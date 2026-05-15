from __future__ import annotations

from pathlib import Path
from uuid import UUID

from src.tasks.base import _push_on_complete, _run_async, pipeline_task
from src.tasks.celery_app import celery_app


@pipeline_task(stage="discovery", queue="scrape")
def run_discovery(*, search_id: str, correlation_id: str) -> dict:
    return _discover(search_id)


def _discover(search_id: str) -> dict:
    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.data.repositories.saved_searches import SavedSearchesRepository
    from src.matcher.engine import JobMatcher
    from src.observability.logging import get_logger
    from src.scraper.service import ScraperService
    from src.utils.config import SearchQueryConfig, load_config

    log = get_logger("tasks.discovery")
    config = load_config(Path("config.yaml"))

    async def _load():
        maker = get_sessionmaker()
        async with maker() as session:
            return await SavedSearchesRepository(session).get_by_id(UUID(search_id))

    saved = _run_async(_load)
    if saved is None:
        return {"jobs_scraped": 0, "new_matches": 0}

    queries = [SearchQueryConfig(keywords=saved.keywords, location=saved.location)]
    sources = saved.sources if saved.sources else None

    service = ScraperService(config, Path("."), log)
    jobs = service.scrape(queries=queries, sources=sources)

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

    count = _run_async(_persist)

    matcher = JobMatcher(config, Path("."), log)

    async def _match() -> list:
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobsRepository(session)
            new_jobs = await repo.list_by_status("new", limit=500)
            ranked = matcher.rank(new_jobs)
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
            return ranked

    ranked = _run_async(_match)
    min_score = saved.min_match_score
    new_matches = sum(1 for r in ranked if (r.score or 0.0) >= min_score)

    if new_matches > 0:
        _push_discovery_notification(saved.keywords, new_matches)

    async def _update_ts():
        maker = get_sessionmaker()
        async with maker() as session:
            repo = SavedSearchesRepository(session)
            row = await repo.get_by_id(UUID(search_id))
            if row:
                await repo.mark_run(row)
            await session.commit()

    _run_async(_update_ts)

    return {"jobs_scraped": count, "new_matches": new_matches}


def _push_discovery_notification(keywords: str, new_matches: int) -> None:
    try:
        from src.data.db import get_sessionmaker
        from src.data.repositories.fcm_tokens import FcmTokensRepository
        from src.notifications.push import PushEvent

        async def _get_tokens() -> list[str]:
            maker = get_sessionmaker()
            async with maker() as session:
                repo = FcmTokensRepository(session)
                rows = await repo.list_all()
                return [r.token for r in rows]

        tokens = _run_async(_get_tokens)

        from src.tasks.base import _build_push_service
        svc = _build_push_service()
        svc.send_event(
            PushEvent(
                title=f"{new_matches} new job{'s' if new_matches != 1 else ''} found",
                body=f"Matches for: {keywords}",
                data={"kind": "discovery", "new_matches": str(new_matches)},
            ),
            tokens=tokens,
        )
    except Exception:
        pass


@celery_app.task(name="src.tasks.discovery.run_due_searches", queue="scrape")
def run_due_searches() -> dict:
    import uuid

    from src.data.db import get_sessionmaker
    from src.data.repositories.saved_searches import SavedSearchesRepository
    from src.observability.logging import get_logger

    log = get_logger("tasks.discovery")

    async def _list_due():
        maker = get_sessionmaker()
        async with maker() as session:
            return await SavedSearchesRepository(session).list_due()

    due = _run_async(_list_due)
    log.info("discovery.due_searches", count=len(due))

    for search in due:
        correlation_id = str(uuid.uuid4())
        run_discovery.delay(search_id=str(search.id), correlation_id=correlation_id)

    return {"dispatched": len(due)}
