from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        stmt = (
            insert(Integration)
            .values(
                provider=provider,
                status=status,
                last_error=last_error,
            )
            .on_conflict_do_update(
                index_elements=["provider"],
                set_={
                    "status": status,
                    "last_error": last_error,
                },
            )
            .returning(Integration)
        )
        result = await self.session.execute(
            stmt, execution_options={"populate_existing": True}
        )
        return result.scalar_one()
