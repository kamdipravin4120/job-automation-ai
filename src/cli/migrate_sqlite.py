"""One-shot importer from the legacy SQLite tracking DB into Postgres.
Lossless-on-retry: skips rows that already exist by id."""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from src.data.db import get_sessionmaker
from src.data.models.application import Application
from src.observability.logging import get_logger

log = get_logger("cli.migrate_sqlite")


def run(*, source: str) -> int:
    path = Path(source)
    if not path.exists():
        log.warning("migrate_sqlite.missing_source", source=source)
        return 0  # Nothing to migrate is not an error.

    # If called from inside a running event loop (tests), offload to a thread
    # with its own loop; asyncio.run() cannot nest.
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return asyncio.run(_migrate(path))

    import threading

    from src.data.db import get_engine, reset_engine_cache

    result: dict = {}

    async def _driver() -> int:
        try:
            return await _migrate(path)
        finally:
            # Dispose before loop closes so asyncpg doesn't schedule cleanup
            # work on a dead loop.
            await get_engine().dispose()

    def _runner() -> None:
        reset_engine_cache()
        try:
            result["rc"] = asyncio.run(_driver())
        except BaseException as exc:
            result["exc"] = exc

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    if "exc" in result:
        raise result["exc"]
    return result.get("rc", 0)


async def _migrate(path: Path) -> int:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    rows = list(con.execute("SELECT * FROM applications"))
    con.close()

    maker = get_sessionmaker()
    async with maker() as session:
        for row in rows:
            row_id = _to_uuid(row["id"])
            existing = await session.execute(
                select(Application).where(Application.id == row_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                Application(
                    id=row_id,
                    job_id=_to_uuid(row["job_id"]),
                    submitted_at=_parse_dt(row["submitted_at"]),
                    channel=row["channel"] or "easy_apply",
                    current_status=row["status"] or "submitted",
                    status_history=[],
                    notes=row["notes"] or "",
                )
            )
        await session.commit()
    log.info("migrate_sqlite.done", imported=len(rows))
    return 0


def _to_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, value or "legacy")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0)
