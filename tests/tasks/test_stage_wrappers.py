from unittest.mock import patch

import pytest

from src.tasks.apply import run_apply
from src.tasks.match import run_match
from src.tasks.scrape import run_scrape
from src.tasks.tailor import run_tailor


@pytest.mark.asyncio(loop_scope="session")
async def test_run_scrape_invokes_scraper_service_and_persists(
    celery_app_eager, db_session
):
    with patch("src.tasks.scrape._scrape_and_persist") as mock_impl:
        mock_impl.return_value = {"jobs_scraped": 3}
        result = run_scrape.apply(kwargs={"correlation_id": "s-1"}).get()
    assert result == {"jobs_scraped": 3}
    mock_impl.assert_called_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_run_match_invokes_matcher(celery_app_eager, db_session):
    with patch("src.tasks.match._match_all") as mock_impl:
        mock_impl.return_value = {"jobs_ranked": 7}
        assert run_match.apply(kwargs={"correlation_id": "m-1"}).get() == {
            "jobs_ranked": 7
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_run_tailor_targets_a_job(celery_app_eager, db_session):
    with patch("src.tasks.tailor._tailor_for_job") as mock_impl:
        mock_impl.return_value = {"artifacts_written": 3}
        assert run_tailor.apply(
            kwargs={"correlation_id": "t-1", "job_id": "job-uuid"}
        ).get() == {"artifacts_written": 3}


@pytest.mark.asyncio(loop_scope="session")
async def test_run_apply_targets_a_job(celery_app_eager, db_session):
    with patch("src.tasks.apply._apply_to_job") as mock_impl:
        mock_impl.return_value = {"submitted": True}
        assert run_apply.apply(
            kwargs={"correlation_id": "a-1", "job_id": "job-uuid"}
        ).get() == {"submitted": True}
