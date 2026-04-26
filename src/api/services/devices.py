from __future__ import annotations

import time
import uuid

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.devices import DevicesRepository


async def revoke_device(
    *,
    db: AsyncSession,
    redis: aioredis.Redis,
    device_id: uuid.UUID,
    current_jti: str | None = None,
    token_exp: int | None = None,
) -> None:
    repo = DevicesRepository(db)
    await repo.revoke(device_id)
    await db.commit()

    if current_jti and token_exp:
        remaining = int(token_exp - time.time())
        if remaining > 0:
            await redis.setex(f"revoked:jti:{current_jti}", remaining, "1")
