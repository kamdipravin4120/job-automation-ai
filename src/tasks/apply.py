"""Apply stage wrapper. Uses existing LinkedInEasyApplyBot flow unchanged."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="apply", max_retries=1, queue="browser")
def run_apply(*, correlation_id: str, job_id: str) -> dict:
    return _apply_to_job(correlation_id, job_id)


def _apply_to_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.apply.linkedin_easy_apply import LinkedInEasyApplyBot
    from src.observability.logging import get_logger
    from src.utils.config import load_config

    log = get_logger("tasks.apply")
    config = load_config(Path("config.yaml"))
    flow = LinkedInEasyApplyBot(config, Path("."), log)
    submitted = flow.apply_by_job_id(job_id=job_id)
    return {"submitted": bool(submitted)}
