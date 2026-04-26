from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.applications import ApplicationOut
from src.api.schemas.common import PaginatedResponse
from src.data.db import get_sessionmaker
from src.data.repositories.applications import ApplicationsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[ApplicationOut])
async def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = ApplicationsRepository(db)
    items, total = await repo.list_paginated(page=page, per_page=per_page, status=status)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             has_next=(page * per_page) < total)


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: uuid.UUID, _device=Depends(get_current_device), db=Depends(_get_db),
):
    app = await ApplicationsRepository(db).get_by_id(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app
