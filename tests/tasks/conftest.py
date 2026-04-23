import pytest


@pytest.fixture
def celery_app_eager():
    """Run tasks synchronously in-process for tests.

    propagates=False so autoretry_for can drive its retry loop in-process
    (Retry exceptions stay internal). .get() still raises terminal errors
    (UserActionRequiredError / LLMValidationError) after max_retries.
    """
    from src.tasks import celery_app as mod

    mod.celery_app.conf.task_always_eager = True
    mod.celery_app.conf.task_eager_propagates = False
    yield mod.celery_app
    mod.celery_app.conf.task_always_eager = False
