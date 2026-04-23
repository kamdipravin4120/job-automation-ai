"""Scrape stage wrapper. Delegates to existing scraper service;
persists jobs via JobsRepository. Body is intentionally thin — W4 adds
selector self-healing into the 0-results path."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="scrape", max_retries=2, queue="scrape")
def run_scrape(*, correlation_id: str) -> dict:
    return _scrape_and_persist(correlation_id)


def _scrape_and_persist(correlation_id: str) -> dict:
    import asyncio
    from pathlib import Path

    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.observability.logging import get_logger
    from src.scraper.service import ScraperService
    from src.utils.config import load_config

    log = get_logger("tasks.scrape")
    config = load_config(Path("config.yaml"))
    service = ScraperService(config, Path("."), log)
    jobs = service.scrape()

    async def _persist() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobsRepository(session)
            for j in jobs:
                await repo.upsert(
                    source=j.source,
                    source_id=j.job_id,
                    title=j.title,
                    company=j.company,
                    jd_text=j.description or "",
                    url=j.url,
                )
            await session.commit()
        return len(jobs)

    count = asyncio.run(_persist())
    return {"jobs_scraped": count}
