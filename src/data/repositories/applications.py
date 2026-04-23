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
