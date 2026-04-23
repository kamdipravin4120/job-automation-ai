import os

# Module-level env stubs so modules that call get_settings() at import time
# (e.g. src/tasks/celery_app.py) can be collected by pytest. The testcontainers
# fixtures overwrite DATABASE_URL/CELERY_* with real URLs before any test runs.
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://stub:stub@localhost:1/stub")
os.environ.setdefault("CELERY_BROKER_URL", "redis://stub:1/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://stub:1/0")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402
from testcontainers.redis import RedisContainer  # noqa: E402


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
    # Stubs from module load time are replaced; invalidate caches so downstream
    # code picks up the real testcontainers URLs on first use.
    from src import settings as _settings_mod
    from src.data import db as _db_mod

    _settings_mod.get_settings.cache_clear()
    _db_mod.reset_engine_cache()
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
