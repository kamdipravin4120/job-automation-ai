from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.application import Application
from src.data.models.job import Job


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

    async def get_by_id_with_job(self, app_id) -> tuple[Application, Job | None] | None:
        from sqlalchemy import select
        stmt = (
            select(Application, Job)
            .outerjoin(Job, Application.job_id == Job.id)
            .where(Application.id == app_id)
        )
        row = (await self.session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

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

    async def list_paginated_with_jobs(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
    ) -> tuple[list[tuple[Application, Job | None]], int]:
        from sqlalchemy import func, select

        stmt = select(Application, Job).outerjoin(Job, Application.job_id == Job.id)
        count_stmt = select(func.count()).select_from(Application)
        if status:
            stmt = stmt.where(Application.current_status == status)
            count_stmt = count_stmt.where(Application.current_status == status)
        stmt = stmt.order_by(Application.submitted_at.desc()).offset((page - 1) * per_page).limit(per_page)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = list((await self.session.execute(stmt)))
        return [(r[0], r[1]) for r in rows], total

    async def list_follow_ups(self) -> list[tuple[Application, Job | None]]:
        """Applications needing follow-up: email_status=follow_up_needed OR submitted >7d ago with no email."""
        from sqlalchemy import or_, select
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=7)
        stmt = (
            select(Application, Job)
            .outerjoin(Job, Application.job_id == Job.id)
            .where(
                or_(
                    Application.email_status == "follow_up_needed",
                    (Application.submitted_at < cutoff) & (Application.email_status.is_(None)),
                )
            )
            .where(
                or_(
                    Application.next_follow_up_at.is_(None),
                    Application.next_follow_up_at <= datetime.now(UTC),
                )
            )
            .order_by(Application.submitted_at.asc())
        )
        rows = list(await self.session.execute(stmt))
        return [(r[0], r[1]) for r in rows]
