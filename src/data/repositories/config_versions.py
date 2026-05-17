from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.config_version import ConfigVersion


class ConfigVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, actor: str, diff_patch: str) -> ConfigVersion:
        row = ConfigVersion(actor=actor, diff_patch=diff_patch)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_recent(self, *, limit: int = 10) -> list[ConfigVersion]:
        stmt = (
            select(ConfigVersion)
            .order_by(ConfigVersion.applied_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())
