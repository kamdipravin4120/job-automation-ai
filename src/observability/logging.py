"""Structlog configuration. Call configure_logging() once at process start.
JSON output in production, key-value in dev."""
from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog

LogFormat = Literal["json", "kv"]


def configure_logging(level: str = "INFO", format: LogFormat = "json") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level.upper(),
    )
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_correlation(correlation_id: str, **extra: object) -> None:
    """Bind a correlation_id to the current contextvars-scoped logger.
    All subsequent log calls in this task/request inherit it."""
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id, **extra)


def clear_correlation() -> None:
    structlog.contextvars.clear_contextvars()
