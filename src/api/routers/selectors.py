from __future__ import annotations

import pathlib
import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.selectors import SelectorOverrideOut
from src.data.db import get_sessionmaker
from src.data.repositories.selector_overrides import SelectorOverridesRepository
from src.settings import get_settings

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


def _overrides_path() -> pathlib.Path:
    base = pathlib.Path(get_settings().config_path)
    return base.parent / "config.overrides.yaml"


@router.get("", response_model=list[SelectorOverrideOut])
async def list_pending_selectors(
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    return await repo.list_pending()


@router.post("/{selector_id}/approve", response_model=SelectorOverrideOut)
async def approve_selector(
    selector_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    updated = await repo.approve(selector_id)
    if updated is None:
        raise HTTPException(404, detail="Selector override not found")
    await db.commit()

    overrides_path = _overrides_path()
    existing: dict = {}
    if overrides_path.exists():
        existing = yaml.safe_load(overrides_path.read_text()) or {}
    existing[updated.key_path] = updated.selector
    overrides_path.write_text(yaml.dump(existing, default_flow_style=False))

    return updated


@router.post("/{selector_id}/reject", response_model=SelectorOverrideOut)
async def reject_selector(
    selector_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    updated = await repo.reject(selector_id)
    if updated is None:
        raise HTTPException(404, detail="Selector override not found")
    await db.commit()
    return updated
