"""Scrape stage wrapper. Delegates to existing scraper service;
persists jobs via JobsRepository. Body is intentionally thin — W4 adds
selector self-healing into the 0-results path."""
from __future__ import annotations

from pathlib import Path

from src.data.db import get_sessionmaker
from src.data.repositories.jobs import JobsRepository
from src.data.repositories.runs import RunsRepository
from src.observability.logging import get_logger
from src.scraper.service import ScraperService
from src.tasks.base import _run_async, pipeline_task
from src.utils.config import load_config


@pipeline_task(stage="scrape", max_retries=2, queue="scrape")
def run_scrape(*, correlation_id: str) -> dict:
    return _scrape_and_persist(correlation_id)


def _scrape_and_persist(correlation_id: str) -> dict:
    log = get_logger("tasks.scrape")
    config = load_config(Path("config.yaml"))
    service = ScraperService(config, Path("."), log)
    jobs = service.scrape()

    async def _persist() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            jobs_repo = JobsRepository(session)
            for j in jobs:
                await jobs_repo.upsert(
                    source=j.source,
                    source_id=j.job_id,
                    title=j.title,
                    company=j.company,
                    jd_text=j.description or "",
                    url=j.url,
                )
            count = len(jobs)
            runs_repo = RunsRepository(session)
            run, _ = await runs_repo.get_or_create(kind="scrape", correlation_id=correlation_id)
            await runs_repo.set_jobs_found(run.id, count)
            await session.commit()
        return count

    count = _run_async(_persist)
    return {"jobs_scraped": count}
