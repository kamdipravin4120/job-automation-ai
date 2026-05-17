from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.runs import RunOut
from src.data.db import get_sessionmaker
from src.data.repositories.runs import RunsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[RunOut])
async def list_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    items, total = await repo.list_paginated(page=page, per_page=per_page, status=status)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             has_next=(page * per_page) < total)


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, _device=Depends(get_current_device), db=Depends(_get_db)):
    run = await RunsRepository(db).get_by_id(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run
