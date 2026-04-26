import pytest

from src.errors import (
    AuthenticationExpiredError,
    ExternalServiceError,
    LLMValidationError,
    PipelineError,
    RateLimitExceededError,
    SelectorBrokenError,
    UserActionRequiredError,
)


def test_every_error_has_stable_code():
    errors = [
        PipelineError("x"),
        ExternalServiceError("x", service="openai"),
        SelectorBrokenError("x", source="linkedin"),
        LLMValidationError("x", kind="tailored_resume", complaint="missing keys"),
        AuthenticationExpiredError("x", service="linkedin"),
        RateLimitExceededError("x", service="openai", retry_after_seconds=30),
        UserActionRequiredError("x", required="linkedin_2fa"),
    ]
    codes = {err.error_code for err in errors}
    assert len(codes) == len(errors), "error_code must be unique per class"
    for err in errors:
        assert isinstance(err.error_code, str) and err.error_code.isupper()


def test_error_serializes_to_api_envelope():
    err = RateLimitExceededError("too fast", service="openai", retry_after_seconds=30)
    payload = err.to_api_error()
    assert payload == {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "too fast",
        "details": {"service": "openai", "retry_after_seconds": 30},
    }


def test_subclass_of_pipeline_error():
    with pytest.raises(PipelineError):
        raise SelectorBrokenError("broken", source="naukri")
