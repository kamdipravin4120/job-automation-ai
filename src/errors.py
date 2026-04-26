"""Typed error hierarchy. Every raise sets a stable error_code that the API
and UI can match on. New error classes MUST set ERROR_CODE."""
from __future__ import annotations

from typing import Any


class PipelineError(Exception):
    """Base class for all domain errors raised by the pipeline."""

    ERROR_CODE = "PIPELINE_ERROR"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details

    @property
    def error_code(self) -> str:
        return self.ERROR_CODE

    def to_api_error(self) -> dict[str, Any]:
        return {
            "code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ExternalServiceError(PipelineError):
    ERROR_CODE = "EXTERNAL_SERVICE_ERROR"

    def __init__(self, message: str, *, service: str, **details: Any) -> None:
        super().__init__(message, service=service, **details)


class SelectorBrokenError(PipelineError):
    ERROR_CODE = "SELECTOR_BROKEN"

    def __init__(self, message: str, *, source: str, **details: Any) -> None:
        super().__init__(message, source=source, **details)


class LLMValidationError(PipelineError):
    ERROR_CODE = "LLM_VALIDATION_FAILED"

    def __init__(self, message: str, *, kind: str, complaint: str, **details: Any) -> None:
        super().__init__(message, kind=kind, complaint=complaint, **details)


class AuthenticationExpiredError(PipelineError):
    ERROR_CODE = "AUTHENTICATION_EXPIRED"

    def __init__(self, message: str, *, service: str, **details: Any) -> None:
        super().__init__(message, service=service, **details)


class RateLimitExceededError(PipelineError):
    ERROR_CODE = "RATE_LIMIT_EXCEEDED"

    def __init__(
        self, message: str, *, service: str, retry_after_seconds: int, **details: Any
    ) -> None:
        super().__init__(
            message, service=service, retry_after_seconds=retry_after_seconds, **details
        )


class UserActionRequiredError(PipelineError):
    ERROR_CODE = "USER_ACTION_REQUIRED"

    def __init__(self, message: str, *, required: str, **details: Any) -> None:
        super().__init__(message, required=required, **details)
