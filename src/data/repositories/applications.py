from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.application import Application


class ApplicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        channel: str,
        external_ref: str | None = None,
    ) -> Application:
        row = Application(
            job_id=job_id,
            submitted_at=datetime.now(UTC),
            channel=channel,
            external_ref=external_ref,
            current_status="submitted",
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_id(self, app_id) -> Application | None:
        return await self.session.get(Application, app_id)

    async def set_status(self, application: Application, *, status: str) -> None:
        application.status_history = (application.status_history or []) + [
            {
                "from": application.current_status,
                "to": status,
                "at": datetime.now(UTC).isoformat(),
            }
        ]
        application.current_status = status

    async def list_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
    ) -> tuple[list[Application], int]:
        from sqlalchemy import func, select

        stmt = select(Application)
        count_stmt = select(func.count()).select_from(Application)
        if status:
            stmt = stmt.where(Application.current_status == status)
            count_stmt = count_stmt.where(Application.current_status == status)
        stmt = stmt.order_by(Application.submitted_at.desc()).offset((page - 1) * per_page).limit(per_page)
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars())
        return items, total
