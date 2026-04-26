import os
import subprocess
import sys

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio(loop_scope="session")
async def test_alembic_upgrade_head_produces_full_schema(monkeypatch, pg_container):
    sync_url = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    monkeypatch.setenv("DATABASE_URL", async_url)

    # sys.executable -m alembic (vs bare "alembic") avoids broken venv shebangs
    # and guarantees the same interpreter pytest is using.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert result.returncode == 0, result.stderr

    from src.data.db import get_engine, reset_engine_cache

    reset_engine_cache()
    engine = get_engine()
    async with engine.connect() as conn:
        def _names(sync_conn):
            return sorted(inspect(sync_conn).get_table_names())
        names = await conn.run_sync(_names)
    assert "runs" in names
    assert "applications" in names
    assert "alembic_version" in names
