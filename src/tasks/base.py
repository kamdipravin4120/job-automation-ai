"""@pipeline_task — decorator that wraps every pipeline stage with:
- idempotency keyed by (stage, correlation_id): second call returns early.
- typed error dispatch: retry ExternalServiceError, don't retry
  UserActionRequiredError / LLMValidationError.
- audit trail: creates/updates a row in `runs`.
- PII scrubbing: only allowlisted keys from exc.details are persisted or
  surfaced to the API envelope.

Full self-correcting framework (daily caps, DLQ diagnosis) lands in W4.
W1 ships the idempotency + retry core + PII guardrail.
"""
from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any

from celery import Task

from src.errors import (
    ExternalServiceError,
    LLMValidationError,
    PipelineError,
    RateLimitExceededError,
    UserActionRequiredError,
)
from src.observability.logging import bind_correlation, clear_correlation, get_logger
from src.tasks.celery_app import celery_app

log = get_logger("tasks.base")

DO_NOT_RETRY = (UserActionRequiredError, LLMValidationError)


def _build_push_service():
    from src.notifications.push import PushService
    from src.settings import get_settings
    s = get_settings()
    return PushService(
        ntfy_topic_url=s.ntfy_topic_url,
        fcm_project_id=s.fcm_project_id,
        fcm_service_account_json=s.fcm_service_account_json,
    )


def _push_on_complete(stage: str, result: dict) -> None:
    """Fire a push notification after a pipeline stage completes. Never raises."""
    try:
        from src.data.db import get_sessionmaker
        from src.data.repositories.fcm_tokens import FcmTokensRepository
        from src.notifications.push import PushEvent

        async def _get_tokens() -> list[str]:
            maker = get_sessionmaker()
            async with maker() as session:
                repo = FcmTokensRepository(session)
                rows = await repo.list_all()
                return [r.token for r in rows]

        tokens = _run_async(_get_tokens)

        svc = _build_push_service()
        body_parts = [f"Stage: {stage}"]
        for k, v in list(result.items())[:2]:
            body_parts.append(f"{k}: {v}")
        svc.send_event(PushEvent(
            title=f"Pipeline: {stage} complete",
            body=" | ".join(body_parts),
            data={"kind": stage, **result},
        ), tokens=tokens)
    except Exception:
        log.debug("Push notification skipped (not configured or error)", exc_info=True)

# Keys we'll accept from arbitrary PipelineError.details payloads without
# worrying about leaking secrets or PII into the runs table / API envelope.
# Anything else is replaced with the string "<redacted>". Extend deliberately.
SAFE_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "service",
        "source",
        "kind",
        "complaint",
        "required",
        "retry_after_seconds",
        "type",
        "message",
        "status_code",
        "attempt",
        "stage",
        "error_code",
    }
)


def filter_error_details(details: dict[str, Any] | None) -> dict[str, Any]:
    """Drop any key not in SAFE_DETAIL_KEYS. Prevents PII/secret leakage from
    upstream PipelineError.details into persisted runs rows and API responses."""
    if not details:
        return {}
    return {k: v for k, v in details.items() if k in SAFE_DETAIL_KEYS}


def pipeline_task(
    *,
    stage: str,
    max_retries: int = 2,
    queue: str = "scrape",
    retry_backoff: int = 5,
    retry_backoff_max: int = 300,
):
    def decorator(fn: Callable) -> Task:
        @celery_app.task(
            bind=True,
            name=f"pipeline.{stage}.{fn.__name__}",
            queue=queue,
            acks_late=True,
            autoretry_for=(ExternalServiceError, RateLimitExceededError),
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            retry_backoff_max=retry_backoff_max,
            retry_jitter=True,
        )
        @functools.wraps(fn)
        def wrapper(self: Task, *args: Any, **kwargs: Any):
            correlation_id: str | None = kwargs.get("correlation_id")
            if correlation_id is None:
                raise ValueError(
                    f"@pipeline_task '{stage}' requires keyword-only 'correlation_id'"
                )
            task_id = self.request.id if self.request else None
            bind_correlation(correlation_id, stage=stage, task_id=task_id)
            try:
                created = _mark_run_running_sync(
                    stage=stage, correlation_id=correlation_id
                )
                if not created:
                    log.info("pipeline_task.skip_duplicate", correlation_id=correlation_id)
                    return None
                result = fn(*args, **kwargs)
                _mark_run_succeeded_sync(stage=stage, correlation_id=correlation_id)
                _push_on_complete(stage=stage, result=result if isinstance(result, dict) else {})
                return result
            except DO_NOT_RETRY as exc:
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code=exc.error_code,
                    error_details=filter_error_details(exc.details),
                )
                raise
            except PipelineError as exc:
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code=exc.error_code,
                    error_details=filter_error_details(exc.details),
                )
                raise
            except Exception as exc:  # pragma: no cover - safety net
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code="UNHANDLED",
                    error_details=filter_error_details(
                        {"type": type(exc).__name__, "message": str(exc)}
                    ),
                )
                raise
            finally:
                # MUST run in finally — Celery prefork workers reuse the same
                # process for the next task. Without this, contextvars leak
                # the prior task's correlation_id into the next one's logs.
                clear_correlation()

        return wrapper

    return decorator


# -- Synchronous helpers over the async repo --------------------------------

def _run_async(coro_factory):
    """Drive an async coroutine to completion from sync code (Celery task body).

    Accepts a zero-arg factory rather than a coroutine so the coroutine is
    created inside the target event loop (asyncpg connections bind to the loop
    that opened them — creating the coro in a different loop than the one that
    executes it triggers 'Future attached to a different loop').

    Handles two contexts:
      (1) Celery worker, no running loop — asyncio.run works directly.
      (2) pytest-asyncio test that .apply()s the task from inside its own loop
          — asyncio.run would raise "cannot be called from a running event
          loop", so we offload to a helper thread that runs its own loop.

    Before running, the SQLAlchemy engine cache is cleared so each invocation
    gets a fresh engine bound to the current loop. Cheap in tests; acceptable
    in workers where each task is independent anyway.
    """
    import threading

    from src.data.db import reset_engine_cache

    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    async def _driver():
        from src.data.db import get_engine

        try:
            return await coro_factory()
        finally:
            # Dispose before the loop closes so asyncpg connections don't
            # schedule cleanup work on a dead loop.
            await get_engine().dispose()

    def _target():
        reset_engine_cache()
        return asyncio.run(_driver())

    if not in_loop:
        return _target()

    result: dict[str, Any] = {}

    def _runner() -> None:
        try:
            result["value"] = _target()
        except BaseException as exc:  # re-raised on main thread
            result["exc"] = exc

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    if "exc" in result:
        raise result["exc"]
    return result.get("value")


def _mark_run_running_sync(*, stage: str, correlation_id: str) -> bool:
    async def _inner() -> bool:
        from src.data.db import get_sessionmaker
        from src.data.repositories.runs import RunsRepository

        maker = get_sessionmaker()
        async with maker() as session:
            repo = RunsRepository(session)
            run, created = await repo.get_or_create(
                kind=stage, correlation_id=correlation_id
            )
            if created:
                await repo.mark_running(run)
            elif run.status == "succeeded":
                await session.commit()
                return False
            await session.commit()
            return True

    return _run_async(_inner)


def _mark_run_succeeded_sync(*, stage: str, correlation_id: str) -> None:
    async def _inner():
        from src.data.db import get_sessionmaker
        from src.data.repositories.runs import RunsRepository

        maker = get_sessionmaker()
        async with maker() as session:
            repo = RunsRepository(session)
            run, _ = await repo.get_or_create(kind=stage, correlation_id=correlation_id)
            await repo.mark_succeeded(run)
            await session.commit()

    _run_async(_inner)


def _mark_run_failed_sync(
    *, stage: str, correlation_id: str, error_code: str, error_details: dict
) -> None:
    async def _inner():
        from src.data.db import get_sessionmaker
        from src.data.repositories.runs import RunsRepository

        maker = get_sessionmaker()
        async with maker() as session:
            repo = RunsRepository(session)
            run, _ = await repo.get_or_create(kind=stage, correlation_id=correlation_id)
            await repo.mark_failed(
                run, error_code=error_code, error_details=error_details
            )
            await session.commit()

    _run_async(_inner)
