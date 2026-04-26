from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.integration import Integration


class IntegrationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Integration]:
        result = await self.session.execute(
            select(Integration).order_by(Integration.provider)
        )
        return list(result.scalars())

    async def get(self, provider: str) -> Integration | None:
        return await self.session.get(Integration, provider)

    async def upsert(
        self,
        *,
        provider: str,
        status: str,
        last_error: str | None = None,
    ) -> Integration:
        row = await self.get(provider)
        if row is None:
            row = Integration(provider=provider, status=status, last_error=last_error)
            self.session.add(row)
        else:
            row.status = status
            row.last_error = last_error
        await self.session.flush()
        return row
