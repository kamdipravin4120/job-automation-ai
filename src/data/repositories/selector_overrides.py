from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.selector_override import SelectorOverride


class SelectorOverridesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending(self) -> list[SelectorOverride]:
        stmt = (
            select(SelectorOverride)
            .where(SelectorOverride.status == "pending")
            .order_by(SelectorOverride.proposed_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars())

    async def get(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        return await self.session.get(SelectorOverride, selector_id)

    async def approve(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        row = await self.get(selector_id)
        if row is None:
            return None
        row.status = "approved"
        await self.session.flush()
        return row

    async def reject(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        row = await self.get(selector_id)
        if row is None:
            return None
        row.status = "rejected"
        await self.session.flush()
        return row
