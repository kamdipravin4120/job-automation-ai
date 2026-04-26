"""End-to-end pipeline test: scrape → match → tailor via Celery eager mode.

External services are patched so CI stays hermetic. The runs table
idempotency layer (Postgres) is exercised for real.
"""
from unittest.mock import patch

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_scrape_then_match_then_tailor_roundtrip(db_session, celery_app_eager):
    from src.tasks.match import run_match
    from src.tasks.scrape import run_scrape
    from src.tasks.tailor import run_tailor

    with (
        patch("src.tasks.scrape._scrape_and_persist", return_value={"jobs_scraped": 2}),
        patch("src.tasks.match._match_all", return_value={"jobs_ranked": 2}),
        patch("src.tasks.tailor._tailor_for_job", return_value={"artifacts_written": 3}),
    ):
        run_scrape.apply(kwargs={"correlation_id": "e2e-1"}).get()
        run_match.apply(kwargs={"correlation_id": "e2e-1"}).get()
        r = run_tailor.apply(kwargs={"correlation_id": "e2e-1", "job_id": "j-1"}).get()

    assert r == {"artifacts_written": 3}
