from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.core.deps import get_current_device
from src.api.schemas.audit import AuditEntryOut
from src.api.schemas.common import PaginatedResponse
from src.data.db import get_sessionmaker
from src.data.repositories.audit_logs import AuditLogRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[AuditEntryOut])
async def list_audit(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    actor: str | None = Query(None),
    action: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = AuditLogRepository(db)
    items, total = await repo.list_paginated(
        page=page, per_page=per_page, actor=actor, action=action
    )
    return PaginatedResponse(
        items=items, total=total, page=page, per_page=per_page,
        has_next=(page * per_page) < total,
    )
