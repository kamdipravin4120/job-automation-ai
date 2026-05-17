from __future__ import annotations

import pathlib
from difflib import unified_diff

import yaml
from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.core.redis_dep import get_redis
from src.api.schemas.config import ConfigOut, ConfigUpdateRequest
from src.data.db import get_sessionmaker
from src.data.repositories.config_versions import ConfigVersionRepository
from src.settings import get_settings

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=ConfigOut)
async def get_config(_device=Depends(get_current_device)):
    config_path = pathlib.Path(get_settings().config_path)
    yaml_text = config_path.read_text() if config_path.exists() else ""
    return ConfigOut(yaml_text=yaml_text)


@router.put("", response_model=ConfigOut)
async def update_config(
    body: ConfigUpdateRequest,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
    redis=Depends(get_redis),
):
    try:
        yaml.safe_load(body.yaml_text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}")

    config_path = pathlib.Path(get_settings().config_path)
    old_text = config_path.read_text() if config_path.exists() else ""

    diff = "".join(
        unified_diff(
            old_text.splitlines(keepends=True),
            body.yaml_text.splitlines(keepends=True),
            fromfile="config.yaml",
            tofile="config.yaml",
        )
    )

    config_path.write_text(body.yaml_text)

    repo = ConfigVersionRepository(db)
    await repo.create(actor=str(_device.id), diff_patch=diff)
    await db.commit()

    await redis.publish("events:config_reload", "{}")
    return ConfigOut(yaml_text=body.yaml_text)
