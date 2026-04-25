import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio(loop_scope="session")
async def test_all_tables_present(db_session):
    engine = db_session.bind
    async with engine.connect() as conn:
        def _inspect(sync_conn):
            return sorted(inspect(sync_conn).get_table_names())
        names = await conn.run_sync(_inspect)
    assert set(names) >= {
        "devices",
        "integrations",
        "jobs",
        "job_artifacts",
        "applications",
        "runs",
        "drafts",
        "threads",
        "selector_overrides",
        "audit_log",
        "fcm_tokens",
        "config_versions",
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_runs_has_idempotency_columns(db_session):
    engine = db_session.bind
    async with engine.connect() as conn:
        def _cols(sync_conn):
            return {c["name"] for c in inspect(sync_conn).get_columns("runs")}
        cols = await conn.run_sync(_cols)
    assert {"kind", "correlation_id", "idempotency_key", "status", "steps", "retry_count"} <= cols


@pytest.mark.asyncio(loop_scope="session")
async def test_runs_unique_on_kind_correlation_id(db_session):
    engine = db_session.bind
    async with engine.connect() as conn:
        def _uniques(sync_conn):
            return [
                tuple(sorted(u["column_names"]))
                for u in inspect(sync_conn).get_unique_constraints("runs")
            ]
        uniques = await conn.run_sync(_uniques)
    assert ("correlation_id", "kind") in uniques
