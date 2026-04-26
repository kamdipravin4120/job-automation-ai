from __future__ import annotations

import redis.asyncio as aioredis

from src.settings import get_settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_settings().celery_broker_url, decode_responses=True)
    return _client


async def _close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
