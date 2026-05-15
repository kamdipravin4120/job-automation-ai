from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.searches import SearchIn, SearchOut, SearchPatch
from src.data.db import get_sessionmaker
from src.data.repositories.saved_searches import SavedSearchesRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=list[SearchOut])
async def list_searches(_device=Depends(get_current_device), db=Depends(_get_db)):
    return await SavedSearchesRepository(db).list_all()


@router.post("", response_model=SearchOut, status_code=201)
async def create_search(
    body: SearchIn,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SavedSearchesRepository(db)
    row = await repo.create(
        keywords=body.keywords,
        location=body.location,
        sources=body.sources,
        min_match_score=body.min_match_score,
        enabled=body.enabled,
        run_every_hours=body.run_every_hours,
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{search_id}", response_model=SearchOut)
async def update_search(
    search_id: uuid.UUID,
    body: SearchPatch,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SavedSearchesRepository(db)
    row = await repo.get_by_id(search_id)
    if not row:
        raise HTTPException(404, "Search not found")
    await repo.update(
        row,
        keywords=body.keywords,
        location=body.location,
        sources=body.sources,
        min_match_score=body.min_match_score,
        enabled=body.enabled,
        run_every_hours=body.run_every_hours,
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{search_id}", status_code=204)
async def delete_search(
    search_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SavedSearchesRepository(db)
    row = await repo.get_by_id(search_id)
    if not row:
        raise HTTPException(404, "Search not found")
    await repo.delete(row)
    await db.commit()


@router.post("/{search_id}/run", status_code=202)
async def trigger_search(
    search_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SavedSearchesRepository(db)
    row = await repo.get_by_id(search_id)
    if not row:
        raise HTTPException(404, "Search not found")

    import uuid as _uuid
    correlation_id = str(_uuid.uuid4())
    from src.tasks.discovery import run_discovery
    run_discovery.delay(search_id=str(search_id), correlation_id=correlation_id)
    return {"queued": True, "correlation_id": correlation_id}
