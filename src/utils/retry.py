from __future__ import annotations

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


def retry_sync(
    attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 8.0,
    retry_on: type[Exception] = Exception,
):
    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=min_wait, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retry_on),
    )

