from __future__ import annotations

import uuid

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request

import redis.asyncio as aioredis

from src.api.core.deps import get_current_device
from src.api.core.redis_dep import get_redis
from src.api.services.devices import revoke_device
from src.data.db import get_sessionmaker
from src.data.models.device import Device

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: uuid.UUID,
    request: Request,
    current_device: Device = Depends(get_current_device),
    redis: aioredis.Redis = Depends(get_redis),
    db=Depends(_get_db),
):
    if current_device.id != device_id:
        raise HTTPException(status_code=403, detail="Cannot revoke another device")

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        jti = payload.get("jti")
        exp = payload.get("exp")
    except Exception:
        jti, exp = None, None

    await revoke_device(db=db, redis=redis, device_id=device_id, current_jti=jti, token_exp=exp)
