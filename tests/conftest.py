import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    with RedisContainer("redis:7-alpine") as rd:
        yield rd


@pytest.fixture(scope="session", autouse=True)
def _apply_test_env(pg_container, redis_container, monkeypatch_session):
    # Normalize URL to the async driver SQLAlchemy expects.
    sync_url = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    os.environ["DATABASE_URL"] = async_url
    os.environ["CELERY_BROKER_URL"] = (
        f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    )
    os.environ["CELERY_RESULT_BACKEND"] = os.environ["CELERY_BROKER_URL"]
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test")
    yield


@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session() -> AsyncIterator[AsyncSession]:
    from src.data.db import get_engine, get_sessionmaker
    from src.data.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
