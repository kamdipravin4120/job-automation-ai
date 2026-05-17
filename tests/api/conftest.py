from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis


@pytest_asyncio.fixture(loop_scope="session")
async def async_client(db_session) -> AsyncClient:
    # Ensure settings cache is cleared so test env vars take effect
    from src.settings import get_settings
    get_settings.cache_clear()
    from src.api.app import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def redis_client(redis_container) -> aioredis.Redis:
    url = (
        f"redis://{redis_container.get_container_host_ip()}"
        f":{redis_container.get_exposed_port(6379)}/0"
    )
    os.environ["CELERY_BROKER_URL"] = url
    os.environ["CELERY_RESULT_BACKEND"] = url
    return aioredis.from_url(url, decode_responses=True)
