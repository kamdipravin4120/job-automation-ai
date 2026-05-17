from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.saved_search import SavedSearch


class SavedSearchesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        keywords: str,
        location: str,
        sources: list[str],
        min_match_score: float = 0.6,
        enabled: bool = True,
        run_every_hours: int = 24,
    ) -> SavedSearch:
        row = SavedSearch(
            keywords=keywords,
            location=location,
            sources=sources,
            min_match_score=min_match_score,
            enabled=enabled,
            run_every_hours=run_every_hours,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_id(self, search_id: uuid.UUID) -> SavedSearch | None:
        return await self.session.get(SavedSearch, search_id)

    async def list_all(self) -> list[SavedSearch]:
        stmt = select(SavedSearch).order_by(SavedSearch.created_at.desc())
        return list((await self.session.execute(stmt)).scalars())

    async def list_due(self) -> list[SavedSearch]:
        now = datetime.now(UTC)
        stmt = select(SavedSearch).where(
            SavedSearch.enabled.is_(True),
            (SavedSearch.next_run_at.is_(None)) | (SavedSearch.next_run_at <= now),
        )
        return list((await self.session.execute(stmt)).scalars())

    async def update(
        self,
        search: SavedSearch,
        *,
        keywords: str | None = None,
        location: str | None = None,
        sources: list[str] | None = None,
        min_match_score: float | None = None,
        enabled: bool | None = None,
        run_every_hours: int | None = None,
    ) -> SavedSearch:
        if keywords is not None:
            search.keywords = keywords
        if location is not None:
            search.location = location
        if sources is not None:
            search.sources = sources
        if min_match_score is not None:
            search.min_match_score = min_match_score
        if enabled is not None:
            search.enabled = enabled
        if run_every_hours is not None:
            search.run_every_hours = run_every_hours
        return search

    async def mark_run(self, search: SavedSearch) -> None:
        now = datetime.now(UTC)
        search.last_run_at = now
        search.next_run_at = now + timedelta(hours=search.run_every_hours)

    async def delete(self, search: SavedSearch) -> None:
        await self.session.delete(search)
