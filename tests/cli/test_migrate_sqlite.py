import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from src.cli.migrate_sqlite import run as migrate_run
from src.data.db import get_sessionmaker
from src.data.models.application import Application


@pytest.fixture
def sqlite_fixture(tmp_path: Path) -> Path:
    db = tmp_path / "tracking.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        """CREATE TABLE applications (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            submitted_at TEXT,
            channel TEXT,
            status TEXT,
            notes TEXT
        )"""
    )
    con.execute(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?)",
        ("app-1", "job-1", "2026-01-01T00:00:00Z", "easy_apply", "submitted", ""),
    )
    con.commit()
    con.close()
    return db


@pytest.mark.asyncio(loop_scope="session")
async def test_migrate_imports_applications(sqlite_fixture, db_session):
    rc = migrate_run(source=str(sqlite_fixture))
    assert rc == 0
    maker = get_sessionmaker()
    async with maker() as session:
        rows = (await session.execute(select(Application))).scalars().all()
    assert len(rows) == 1
    assert rows[0].channel == "easy_apply"
