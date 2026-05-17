from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.dlq import DLQItemOut
from src.data.db import get_sessionmaker
from src.data.repositories.runs import RunsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[DLQItemOut])
async def list_dlq(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    items, total = await repo.list_paginated(page=page, per_page=per_page, status="failed")
    return PaginatedResponse(
        items=items, total=total, page=page, per_page=per_page,
        has_next=(page * per_page) < total,
    )


@router.post("/{run_id}/retry", status_code=202)
async def retry_dlq_item(
    run_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.status != "failed":
        raise HTTPException(404, detail="DLQ item not found")
    from src.tasks.scrape import run_scrape
    run_scrape.apply_async(kwargs={"correlation_id": run.correlation_id})
    return {"queued": True}


@router.post("/{run_id}/dismiss", status_code=200)
async def dismiss_dlq_item(
    run_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.status != "failed":
        raise HTTPException(404, detail="DLQ item not found")
    run.status = "dismissed"
    await db.commit()
    return {"dismissed": True}
