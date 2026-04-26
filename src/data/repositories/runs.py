from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.run import Run


class RunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, *, kind: str, correlation_id: str) -> tuple[Run, bool]:
        stmt = select(Run).where(Run.kind == kind, Run.correlation_id == correlation_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing, False
        row = Run(kind=kind, correlation_id=correlation_id, status="queued")
        self.session.add(row)
        await self.session.flush()
        return row, True

    async def mark_running(self, run: Run) -> None:
        run.status = "running"
        run.started_at = datetime.now(UTC)

    async def mark_succeeded(self, run: Run) -> None:
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)

    async def mark_failed(self, run: Run, *, error_code: str, error_details: dict) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_code = error_code
        run.error_details = error_details

    async def list_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
    ) -> tuple[list[Run], int]:
        from sqlalchemy import func, select

        stmt = select(Run)
        count_stmt = select(func.count()).select_from(Run)
        if status:
            stmt = stmt.where(Run.status == status)
            count_stmt = count_stmt.where(Run.status == status)
        stmt = stmt.order_by(Run.started_at.desc().nullslast()).offset((page - 1) * per_page).limit(per_page)

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars())
        return items, total

    async def get_by_id(self, run_id) -> Run | None:
        return await self.session.get(Run, run_id)
