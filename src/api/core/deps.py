from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

import jwt as pyjwt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.core.redis_dep import get_redis
from src.api.core.security import create_jwt, decode_jwt
from src.data.db import get_sessionmaker
from src.data.repositories.devices import DevicesRepository
from src.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


async def get_current_device(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    redis: aioredis.Redis = Depends(get_redis),
    db=Depends(_get_db),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = decode_jwt(credentials.credentials)
        jti = payload["jti"]
        device_id = uuid.UUID(payload["sub"])
        iat = payload["iat"]
    except pyjwt.exceptions.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (pyjwt.exceptions.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    # JTI revocation check
    if await redis.exists(f"revoked:jti:{jti}"):
        raise HTTPException(status_code=401, detail="Token revoked")

    # Load device
    repo = DevicesRepository(db)
    device = await repo.get(device_id)
    if device is None:
        raise HTTPException(status_code=401, detail="Device not found")

    # Device-wide revocation: token issued before revoked_at is invalid
    if device.revoked_at and iat < device.revoked_at.timestamp():
        raise HTTPException(status_code=401, detail="Device revoked")

    # Token rotation: issue new token if approaching expiry
    settings = get_settings()
    iat_dt = datetime.fromtimestamp(iat, tz=UTC)
    if (datetime.now(tz=UTC) - iat_dt).days >= settings.jwt_rotation_days:
        new_token = create_jwt(device_id)
        remaining = int(payload["exp"] - time.time())
        if remaining > 0:
            await redis.setex(f"revoked:jti:{jti}", remaining, "1")
        request.state.next_token = new_token  # TODO: emit as X-Refresh-Token header via response middleware

    # Update last_seen
    await repo.touch(
        device_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    await db.commit()

    return device
