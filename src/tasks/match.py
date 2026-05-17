"""Match stage wrapper. Runs embedding + scoring on jobs with status='new'.
Thin until W4 adds output validation + retries."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="match", max_retries=2, queue="ai")
def run_match(*, correlation_id: str) -> dict:
    return _match_all(correlation_id)


def _match_all(correlation_id: str) -> dict:
    import asyncio
    from pathlib import Path

    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.matcher.engine import JobMatcher
    from src.observability.logging import get_logger
    from src.utils.config import load_config

    log = get_logger("tasks.match")
    config = load_config(Path("config.yaml"))
    service = JobMatcher(config, Path("."), log)

    async def _run() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobsRepository(session)
            jobs = await repo.list_by_status(status="new", limit=500)
            ranked = service.rank(jobs)
            for r in ranked:
                await repo.upsert(
                    source=r.source,
                    source_id=r.job_id,
                    title=r.title,
                    company=r.company,
                    jd_text=r.description or "",
                    url=r.url,
                    match_score=r.score,
                    score_breakdown=r.score_breakdown,
                )
            await session.commit()
            return len(ranked)

    n = asyncio.run(_run())
    return {"jobs_ranked": n}
