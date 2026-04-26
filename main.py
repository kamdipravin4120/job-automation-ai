from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.orchestrator.pipeline import JobApplicationPipeline
from src.tracking.dashboard import launch_dashboard
from src.utils.config import load_config
from src.utils.logging import configure_logging


def _register_worker(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "worker", help="Start a Celery worker for one or more queues."
    )
    p.add_argument("--queues", default="scrape,ai,browser,mail")
    p.add_argument("--concurrency", type=int, default=2)
    p.set_defaults(func=_cmd_worker)


def _cmd_worker(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.tasks.celery_app",
        "worker",
        "-Q",
        args.queues,
        "--concurrency",
        str(args.concurrency),
        "--loglevel",
        "INFO",
    ]
    return subprocess.call(cmd)


def _register_migrate(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("migrate", help="Run Alembic upgrade head.")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_migrate)


def _cmd_migrate(args: argparse.Namespace) -> int:
    if args.dry_run:
        print("Target revision: head")
        return 0
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])


def _register_migrate_sqlite(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "migrate-sqlite",
        help="Import existing SQLite tracking into Postgres.",
    )
    p.add_argument("--from", dest="source", default="artifacts/tracking.sqlite")
    p.set_defaults(func=_cmd_migrate_sqlite)


def _cmd_migrate_sqlite(args: argparse.Namespace) -> int:
    from src.cli.migrate_sqlite import run as _run

    return _run(source=args.source)


def _register_bootstrap(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "bootstrap",
        help="Generate a device-pairing QR code and store secret in Redis.",
    )
    p.set_defaults(func=_cmd_bootstrap)


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    from src.cli.bootstrap import run as _run
    _run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated job application system")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline_parser = subparsers.add_parser("pipeline", help="Run the full pipeline.")
    pipeline_parser.add_argument(
        "--skip-apply",
        action="store_true",
        help="Stop after resume generation and tracking updates.",
    )

    subparsers.add_parser("scrape", help="Only scrape jobs.")
    subparsers.add_parser("match", help="Scrape and rank jobs, then print the top matches.")
    subparsers.add_parser("resume", help="Generate resume assets for the top matches.")

    apply_parser = subparsers.add_parser(
        "apply",
        help="Run the semi-automated LinkedIn Easy Apply flow for tracked matches.",
    )
    apply_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override the configured max applications per run.",
    )

    subparsers.add_parser(
        "sync-notion",
        help="Push local application tracking records into the configured Notion database.",
    )
    subparsers.add_parser("dashboard", help="Launch the Streamlit tracking dashboard.")

    _register_worker(subparsers)
    _register_migrate(subparsers)
    _register_migrate_sqlite(subparsers)
    _register_bootstrap(subparsers)
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    # New func-dispatched subcommands (worker/migrate/migrate-sqlite) skip
    # config + pipeline init entirely — they just orchestrate subprocesses.
    func = getattr(args, "func", None)
    if func is not None:
        rc = func(args)
        if rc:
            sys.exit(rc)
        return

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    logger = configure_logging(config.logging, config_path.parent)

    if args.command == "dashboard":
        launch_dashboard(config_path)
        return

    pipeline = JobApplicationPipeline(config=config, config_path=config_path, logger=logger)

    if args.command == "scrape":
        jobs = pipeline.scrape_jobs()
        logger.info("Scraped %s jobs", len(jobs))
        return

    if args.command == "match":
        matches = pipeline.match_jobs()
        for rank, match in enumerate(matches, start=1):
            logger.info(
                "[%s] %.4f | %s | %s | %s",
                rank,
                match.total_score,
                match.job.title,
                match.job.company,
                match.job.url,
            )
        return

    if args.command == "resume":
        pipeline.generate_resume_assets()
        return

    if args.command == "apply":
        pipeline.apply_to_jobs(limit=args.limit)
        return

    if args.command == "sync-notion":
        pipeline.sync_tracking_records()
        return

    if args.command == "pipeline":
        pipeline.run(skip_apply=args.skip_apply)


if __name__ == "__main__":
    main()
