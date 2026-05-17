from __future__ import annotations

import json
import pathlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.core.deps import get_current_device
from src.settings import get_settings

router = APIRouter()


class ProfileOut(BaseModel):
    data: dict[str, Any]


class ProfileUpdateRequest(BaseModel):
    data: dict[str, Any]


def _profile_path() -> pathlib.Path:
    return pathlib.Path(get_settings().profile_path)


@router.get("", response_model=ProfileOut)
async def get_profile(_device=Depends(get_current_device)):
    p = _profile_path()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileOut(data=json.loads(p.read_text()))


@router.put("", response_model=ProfileOut)
async def update_profile(body: ProfileUpdateRequest, _device=Depends(get_current_device)):
    p = _profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body.data, indent=2, ensure_ascii=False))
    return ProfileOut(data=body.data)
