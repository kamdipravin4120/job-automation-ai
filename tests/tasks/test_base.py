import pytest

from src.errors import ExternalServiceError, UserActionRequiredError
from src.tasks.base import SAFE_DETAIL_KEYS, filter_error_details, pipeline_task

# celery_app_eager fixture lives in tests/tasks/conftest.py


@pytest.mark.asyncio(loop_scope="session")
async def test_pipeline_task_runs_once_for_same_correlation_id(
    celery_app_eager, db_session
):
    calls = []

    @pipeline_task(stage="test_stage", max_retries=0, queue="scrape")
    def fake(correlation_id: str, value: int) -> int:
        calls.append(value)
        return value

    fake.apply(kwargs={"correlation_id": "c1", "value": 1})
    fake.apply(kwargs={"correlation_id": "c1", "value": 2})
    # Second invocation is short-circuited by the existing run record.
    assert calls == [1]


@pytest.mark.asyncio(loop_scope="session")
async def test_pipeline_task_retries_external_service_error(
    celery_app_eager, db_session
):
    attempts = {"n": 0}

    @pipeline_task(stage="flaky", max_retries=2, queue="scrape")
    def flaky(correlation_id: str) -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ExternalServiceError("boom", service="openai")
        return "ok"

    result = flaky.apply(kwargs={"correlation_id": "cx"}).get()
    assert result == "ok"
    assert attempts["n"] == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_pipeline_task_does_not_retry_user_action_required(
    celery_app_eager, db_session
):
    attempts = {"n": 0}

    @pipeline_task(stage="needs_user", max_retries=5, queue="browser")
    def blocked(correlation_id: str) -> None:
        attempts["n"] += 1
        raise UserActionRequiredError("need 2fa", required="linkedin_2fa")

    # Celery's result backend reconstructs exceptions via exc.__class__(*args),
    # which drops UserActionRequiredError's required=... kwarg and falls back
    # to the PipelineError base class. The important invariant is that
    # DO_NOT_RETRY categories raise exactly once and do not autoretry.
    from src.errors import PipelineError

    with pytest.raises(PipelineError):
        blocked.apply(kwargs={"correlation_id": "cy"}).get()
    assert attempts["n"] == 1


def test_filter_error_details_drops_unsafe_keys():
    raw = {
        "service": "openai",
        "api_key": "sk-secret",
        "email": "user@example.com",
        "status_code": 500,
        "authorization": "Bearer t0ken",
        "message": "timeout",
    }
    filtered = filter_error_details(raw)
    assert "api_key" not in filtered
    assert "email" not in filtered
    assert "authorization" not in filtered
    assert filtered["service"] == "openai"
    assert filtered["status_code"] == 500
    assert filtered["message"] == "timeout"
    assert set(filtered.keys()) <= SAFE_DETAIL_KEYS


def test_filter_error_details_handles_none_and_empty():
    assert filter_error_details(None) == {}
    assert filter_error_details({}) == {}
