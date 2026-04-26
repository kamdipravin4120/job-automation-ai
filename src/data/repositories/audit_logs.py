from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        actor: str | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        if actor:
            stmt = stmt.where(AuditLog.actor == actor)
            count_stmt = count_stmt.where(AuditLog.actor == actor)
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.at.desc()).offset((page - 1) * per_page).limit(per_page)
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars())
        return items, total

    async def append(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        details: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(actor=actor, action=action, target=target, details=details)
        self.session.add(row)
        await self.session.flush()
        return row
