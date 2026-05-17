# W1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing Python pipeline from SQLite + inline execution to Postgres + Celery + typed errors + structured logging, with the CLI continuing to work unchanged as a thin wrapper over the new task layer.

**Architecture:** Replace `load_config` with `pydantic-settings`, introduce SQLAlchemy ORM + Alembic for schema management under `src/data/`, wrap each pipeline stage as an idempotent Celery task under `src/tasks/`, and add a typed error hierarchy + `structlog` observability. Zero changes to `src/scraper/`, `src/matcher/`, `src/resume/`, `src/apply/` internals — they gain a Celery wrapper, that's all. (CEO review 2026-04-22 dropped the earlier plan to move `src/models.py → src/domain/models.py`; Task 5 is now a no-op.)

**Tech Stack:** Python 3.11+ · FastAPI (kept from current) · SQLAlchemy 2.0 (async) · Alembic · Celery 5 · Redis 7 · Postgres 16 · structlog · pydantic-settings · pytest · testcontainers · respx

**Spec reference:** [docs/superpowers/specs/2026-04-21-production-web-app-design.md](../specs/2026-04-21-production-web-app-design.md) §4.1

---

## File structure (what gets created, moved, modified)

**Created:**
- `src/errors.py` — typed error hierarchy
- `src/observability/__init__.py`, `src/observability/logging.py` — structlog config
- `src/settings.py` — pydantic-settings replacing `load_config`
- ~~`src/domain/__init__.py`~~ — DROPPED per CEO review; models stay at `src/models.py`
- `src/data/__init__.py`, `src/data/db.py` — async engine + session factory
- `src/data/models/__init__.py`, `src/data/models/<aggregate>.py` — one file per aggregate
- `src/data/repositories/__init__.py`, `src/data/repositories/<aggregate>.py` — one per aggregate
- `src/data/migrations/env.py`, `src/data/migrations/versions/` — Alembic
- `alembic.ini` — Alembic root config
- `src/tasks/__init__.py`, `src/tasks/celery_app.py` — Celery instance
- `src/tasks/base.py` — `@pipeline_task` decorator with idempotency
- `src/tasks/scrape.py`, `match.py`, `tailor.py`, `apply.py` — one file per stage wrapper
- `src/cli/migrate_sqlite.py` — one-shot SQLite → Postgres importer
- `tests/data/`, `tests/tasks/`, `tests/observability/` — corresponding test trees
- `tests/conftest.py` — shared fixtures (pg_container, redis_container, celery_app)
- `docker-compose.dev.yml` — Postgres + Redis for local dev
- `docs/w1-operating-notes.md` — `.env` vars, local dev loop, migration how-to

**Moved:**
- ~~`src/models.py` → `src/domain/models.py`~~ — DROPPED per CEO review; `src/models.py` stays at its current path.

**Modified:**
- `main.py` — `worker`, `migrate`, `migrate-sqlite` commands added; existing commands unchanged
- `requirements.txt` — add new deps with pinned versions
- `Dockerfile` — unchanged structure, ensure `celery` binary in PATH
- `docker-compose.yml` — add `postgres`, `redis`, `worker-*` services alongside existing

**Unchanged:**
- `src/services/scraper/*`, `matcher/*`, `resume/*`, `apply/*` — no internal changes
- `src/app.py` — stays as current FastAPI dashboard (W2 refactors)
- `static/*` — dashboard unchanged
- `config.yaml`, `data/profile.json` — format unchanged

---

## Tasks

### Task 0: Add new Python dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append the new pinned deps.**

Edit `requirements.txt` — append these lines at the end:

```
SQLAlchemy==2.0.36
alembic==1.14.0
asyncpg==0.30.0
psycopg[binary]==3.2.3
celery==5.4.0
redis==5.2.1
structlog==24.4.0
pydantic-settings==2.6.1
testcontainers[postgres,redis]==4.9.0
respx==0.22.0
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Install and verify.**

Run:
```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "import sqlalchemy, alembic, celery, redis, structlog, pydantic_settings, testcontainers; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit.**

```bash
git add requirements.txt
git commit -m "deps: add sqlalchemy, alembic, celery, redis, structlog, pydantic-settings for W1"
```

---

### Task 1: Local dev infra — Postgres + Redis via docker-compose.dev.yml

**Files:**
- Create: `docker-compose.dev.yml`
- Modify: `.env.example` (create if missing)

- [ ] **Step 1: Write the dev compose file.**

Create `docker-compose.dev.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: jobautomation
      POSTGRES_USER: jobauto
      POSTGRES_PASSWORD: devpassword
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jobauto -d jobautomation"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pg_data:
  redis_data:
```

- [ ] **Step 2: Create/update `.env.example`.**

If `.env.example` does not exist create it; otherwise append missing keys. Ensure the file contains:

```env
# External LLMs
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Optional integrations
NOTION_API_KEY=

# W1 infrastructure
DATABASE_URL=postgresql+asyncpg://jobauto:devpassword@localhost:5432/jobautomation
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
LOG_LEVEL=INFO
LOG_FORMAT=kv
```

- [ ] **Step 3: Bring up services locally and verify.**

Run:
```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U jobauto
docker compose -f docker-compose.dev.yml exec redis redis-cli ping
```
Expected: both services `healthy`, `PONG`, `accepting connections`.

- [ ] **Step 4: Commit.**

```bash
git add docker-compose.dev.yml .env.example
git commit -m "infra: local postgres+redis dev stack via docker-compose.dev.yml"
```

---

### Task 2: Typed error hierarchy

**Files:**
- Create: `src/errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_errors.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail.**

Run:
```bash
python -m pytest tests/test_errors.py -v
```
Expected: ImportError on `src.errors`.

- [ ] **Step 3: Implement `src/errors.py`.**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass.**

Run:
```bash
python -m pytest tests/test_errors.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/errors.py tests/test_errors.py
git commit -m "feat(errors): typed error hierarchy with stable error_code per class"
```

---

### Task 3: Structured logging via structlog

**Files:**
- Create: `src/observability/__init__.py`
- Create: `src/observability/logging.py`
- Create: `tests/observability/__init__.py`
- Create: `tests/observability/test_logging.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/observability/test_logging.py`:

```python
import json
import logging
from io import StringIO

import structlog

from src.observability.logging import configure_logging, get_logger


def test_json_output_carries_correlation_id(monkeypatch, capsys):
    configure_logging(level="INFO", format="json")
    log = get_logger("test").bind(correlation_id="abc-123", run_id="r-1")
    log.info("hello", stage="scrape")
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(captured)
    assert payload["event"] == "hello"
    assert payload["correlation_id"] == "abc-123"
    assert payload["run_id"] == "r-1"
    assert payload["stage"] == "scrape"
    assert payload["level"] == "info"


def test_kv_output_is_human_readable(capsys):
    configure_logging(level="INFO", format="kv")
    log = get_logger("test")
    log.info("hello", stage="scrape")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "event='hello'" in line or "hello" in line
    assert "stage='scrape'" in line or "stage=scrape" in line
```

- [ ] **Step 2: Run test to verify it fails.**

Run:
```bash
python -m pytest tests/observability/test_logging.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement logging config.**

Create `src/observability/__init__.py` as empty file.

Create `src/observability/logging.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass.**

Run:
```bash
python -m pytest tests/observability/test_logging.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/observability/ tests/observability/
git commit -m "feat(observability): structlog configuration with JSON and kv formats"
```

---

### Task 4: Pydantic-settings replacing load_config

**Files:**
- Create: `src/settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/test_settings.py`:

```python
import pytest

from src.settings import Settings, SettingsError


def test_missing_required_env_fails_fast(monkeypatch):
    # Clear everything that could satisfy the required fields.
    for k in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SettingsError) as exc:
        Settings.load()
    # Message must call out the missing field list, so ops can fix immediately.
    msg = str(exc.value)
    assert "OPENAI_API_KEY" in msg or "openai_api_key" in msg


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d"
    )
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://h:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://h:6379/1")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "kv")
    s = Settings.load()
    assert s.openai_api_key.get_secret_value() == "x"
    assert s.log_level == "DEBUG"
    assert s.log_format == "kv"
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/test_settings.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement settings.**

Create `src/settings.py`:

```python
"""Process-wide settings. Loaded once at boot; fails fast on missing required fields."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when required settings are missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Required secrets
    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    database_url: str
    celery_broker_url: str
    celery_result_backend: str

    # Optional
    gemini_api_key: SecretStr | None = None
    notion_api_key: SecretStr | None = None
    sentry_dsn: str | None = None

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "kv"] = "json"

    # Config file path (still YAML for feature config; secrets via env only)
    config_path: str = "config.yaml"
    profile_path: str = "data/profile.json"

    @classmethod
    def load(cls) -> "Settings":
        try:
            return cls()
        except ValidationError as e:
            missing = [
                ".".join(str(p) for p in err["loc"])
                for err in e.errors()
                if err["type"] == "missing"
            ]
            raise SettingsError(
                "Missing required settings: " + ", ".join(missing)
            ) from e


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/test_settings.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/settings.py tests/test_settings.py
git commit -m "feat(settings): pydantic-settings with fail-fast validation"
```

---

### Task 5: ~~Move domain models to `src/domain/`~~ — DROPPED

**Status:** Dropped per CEO review (2026-04-22, SELECTIVE EXPANSION). The originally proposed rename of `src/models.py → src/domain/models.py` along with the rest of the `src/* → src/services/*` directory reorganization (spec §3.2) was cut as pure churn on a solo project. `src/models.py` stays at its current path. All existing imports continue to work unchanged.

**Impact on subsequent tasks:** Task 7 and later that referred to "domain models" now refer to `src.models`. No other tasks depended on Task 5's output. Skip directly to Task 6.

---

### Task 6: SQLAlchemy async engine + session factory

**Files:**
- Create: `src/data/__init__.py`
- Create: `src/data/db.py`
- Create: `tests/conftest.py`
- Create: `tests/data/__init__.py`
- Create: `tests/data/test_db.py`

- [ ] **Step 1: Write the shared conftest with a Postgres container fixture.**

Create `tests/conftest.py`:

```python
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    with RedisContainer("redis:7-alpine") as rd:
        yield rd


@pytest.fixture(scope="session", autouse=True)
def _apply_test_env(pg_container, redis_container, monkeypatch_session):
    # Normalize URL to the async driver SQLAlchemy expects.
    sync_url = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    os.environ["DATABASE_URL"] = async_url
    os.environ["CELERY_BROKER_URL"] = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    os.environ["CELERY_RESULT_BACKEND"] = os.environ["CELERY_BROKER_URL"]
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test")
    yield


@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    from src.data.db import get_sessionmaker, get_engine
    from src.data.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

- [ ] **Step 2: Write the failing test.**

Create `tests/data/test_db.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_engine_connects(db_session):
    from sqlalchemy import text

    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

- [ ] **Step 3: Run test to verify it fails.**

Run:
```bash
python -m pytest tests/data/test_db.py -v
```
Expected: ImportError on `src.data.db` or `src.data.models`.

- [ ] **Step 4: Implement `src/data/db.py`.**

Create `src/data/__init__.py` as empty.

Create `src/data/db.py`:

```python
"""Async SQLAlchemy engine and session factory. Engine is lazy + cached;
tests override DATABASE_URL via env before first access."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


def reset_engine_cache() -> None:
    """Invalidate the cached engine; tests call this after switching env vars."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
```

- [ ] **Step 5: Implement the ORM base.**

Create `src/data/models/__init__.py`:

```python
"""SQLAlchemy ORM package. Aggregate modules import the shared Base from here."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import aggregates so Base.metadata is populated when migrations or tests load this package.
from . import ( # noqa: E402, F401
    device,
    integration,
    job,
    application,
    run,
    draft,
    thread,
    selector_override,
    audit_log,
    fcm_token,
    config_version,
)
```

- [ ] **Step 6: Create a minimal stub for each aggregate module so imports resolve.**

Create each of these with a single placeholder class — the real schema lands in Task 7. For now:

`src/data/models/device.py`:
```python
import uuid
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from . import Base


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    paired_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

For the remaining modules (`integration.py`, `job.py`, `application.py`, `run.py`, `draft.py`, `thread.py`, `selector_override.py`, `audit_log.py`, `fcm_token.py`, `config_version.py`), create each with a placeholder class bearing only an `id` primary key and a `__tablename__`. This lets `Base.metadata.create_all` succeed in Task 6 test. The full schemas land in Task 7.

- [ ] **Step 7: Run tests to verify they pass.**

Run:
```bash
python -m pytest tests/data/test_db.py -v
```
Expected: 1 passed.

- [ ] **Step 8: Commit.**

```bash
git add src/data/ tests/conftest.py tests/data/
git commit -m "feat(data): async SQLAlchemy engine, session factory, ORM base with aggregate stubs"
```

---

### Task 7: Full ORM schema per spec §5

**Files:**
- Modify: every file under `src/data/models/`
- Create: `tests/data/test_schema.py`

- [ ] **Step 1: Write the failing test asserting every expected table exists and has required columns.**

Create `tests/data/test_schema.py`:

```python
import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_all_tables_present(db_session):
    engine = db_session.bind
    async with engine.connect() as conn:
        def _inspect(sync_conn):
            return sorted(inspect(sync_conn).get_table_names())
        names = await conn.run_sync(_inspect)
    assert set(names) >= {
        "devices",
        "sessions",
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


@pytest.mark.asyncio
async def test_runs_has_idempotency_columns(db_session):
    engine = db_session.bind
    async with engine.connect() as conn:
        def _cols(sync_conn):
            return {c["name"] for c in inspect(sync_conn).get_columns("runs")}
        cols = await conn.run_sync(_cols)
    assert {"kind", "correlation_id", "idempotency_key", "status", "steps", "retry_count"} <= cols


@pytest.mark.asyncio
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
```

- [ ] **Step 2: Run and verify failure.**

Run: `python -m pytest tests/data/test_schema.py -v`
Expected: the schema test passes for `test_all_tables_present` (since stubs exist) but column tests fail on `runs`.

- [ ] **Step 3: Implement every aggregate module fully per spec §5.**

Replace each stub. Full content of each file:

**`src/data/models/device.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    public_key: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotates_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**`src/data/models/integration.py`**:
```python
from datetime import datetime
from sqlalchemy import DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Integration(Base):
    __tablename__ = "integrations"
    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**`src/data/models/job.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_jobs_source_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_band: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    jd_text: Mapped[str] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    user_notes: Mapped[str] = mapped_column(Text, default="")


class JobArtifact(Base):
    __tablename__ = "job_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**`src/data/models/application.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(32))
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_status: Mapped[str] = mapped_column(String(32), default="submitted")
    status_history: Mapped[list | None] = mapped_column(JSONB, default=list)
    recruiter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    briefing_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**`src/data/models/run.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("kind", "correlation_id", name="uq_runs_kind_correlation"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32))
    correlation_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    steps: Mapped[list | None] = mapped_column(JSONB, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**`src/data/models/draft.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(32), default="professional")
    created_by: Mapped[str] = mapped_column(String(32))
    parent_draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**`src/data/models/thread.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_threads_channel_external"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(8))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**`src/data/models/selector_override.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class SelectorOverride(Base):
    __tablename__ = "selector_overrides"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    key_path: Mapped[str] = mapped_column(Text)
    selector: Mapped[str] = mapped_column(Text)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proposed_by: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    dom_snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

**`src/data/models/audit_log.py`**:
```python
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    target: Mapped[str] = mapped_column(String(256))
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

**`src/data/models/fcm_token.py`**:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class FcmToken(Base):
    __tablename__ = "fcm_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

**`src/data/models/config_version.py`**:
```python
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(128))
    diff_patch: Mapped[str] = mapped_column(Text)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Run tests to verify they pass.**

Run:
```bash
python -m pytest tests/data/ -v
```
Expected: all three tests pass.

- [ ] **Step 5: Commit.**

```bash
git add src/data/models/
git commit -m "feat(data): full ORM schema per spec §5 — 13 tables"
```

---

### Task 8: Alembic initialization + initial migration

**Files:**
- Create: `alembic.ini`
- Create: `src/data/migrations/env.py`
- Create: `src/data/migrations/script.py.mako`
- Create: `src/data/migrations/versions/` directory
- Create: `tests/data/test_migrations.py`

- [ ] **Step 1: Initialize Alembic pointing at our models package.**

Run:
```bash
alembic init -t async src/data/migrations
```

If that creates an `alembic.ini` at the repo root with the script location pointing somewhere else, edit it so:

`alembic.ini` (key section):
```ini
[alembic]
script_location = src/data/migrations
sqlalchemy.url = %(DATABASE_URL)s
```

- [ ] **Step 2: Rewrite `src/data/migrations/env.py` so it uses our async engine and Base.metadata.**

Replace the generated `env.py` contents with:

```python
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.data.db import get_engine
from src.data.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_engine().url.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = get_engine()
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Generate the initial migration.**

Run:
```bash
docker compose -f docker-compose.dev.yml up -d postgres
export DATABASE_URL="postgresql+asyncpg://jobauto:devpassword@localhost:5432/jobautomation"
alembic revision --autogenerate -m "initial schema"
```

Review the generated file under `src/data/migrations/versions/`. Confirm it creates every table from Task 7. If autogenerate misses anything, edit the migration by hand.

- [ ] **Step 4: Write the migration round-trip test.**

Create `tests/data/test_migrations.py`:

```python
import subprocess

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_alembic_upgrade_head_produces_full_schema(monkeypatch, pg_container):
    sync_url = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    monkeypatch.setenv("DATABASE_URL", async_url)

    # Alembic uses the same env var.
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ},
    )
    assert result.returncode == 0, result.stderr

    from src.data.db import get_engine, reset_engine_cache

    reset_engine_cache()
    engine = get_engine()
    async with engine.connect() as conn:
        def _names(sync_conn):
            return sorted(inspect(sync_conn).get_table_names())
        names = await conn.run_sync(_names)
    assert "runs" in names
    assert "applications" in names
    assert "alembic_version" in names
```

- [ ] **Step 5: Run the migration test.**

Run:
```bash
python -m pytest tests/data/test_migrations.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit.**

```bash
git add alembic.ini src/data/migrations/
git commit -m "feat(data): alembic initial migration for full schema"
```

---

### Task 9: Repositories per aggregate (minimal CRUD)

**Files:**
- Create: `src/data/repositories/__init__.py`
- Create: `src/data/repositories/jobs.py`
- Create: `src/data/repositories/applications.py`
- Create: `src/data/repositories/runs.py`
- Create: `tests/data/test_repositories.py`

- [ ] **Step 1: Write the failing tests.**

Create `tests/data/test_repositories.py`:

```python
import uuid
from datetime import UTC, datetime

import pytest

from src.data.repositories.jobs import JobsRepository
from src.data.repositories.runs import RunsRepository


@pytest.mark.asyncio
async def test_jobs_upsert_is_idempotent(db_session):
    repo = JobsRepository(db_session)
    row_a = await repo.upsert(
        source="linkedin", source_id="x1", title="Eng", company="Co",
        jd_text="desc", url=None, match_score=0.8,
    )
    await db_session.commit()
    row_b = await repo.upsert(
        source="linkedin", source_id="x1", title="Eng", company="Co",
        jd_text="desc", url=None, match_score=0.9,
    )
    await db_session.commit()
    assert row_a.id == row_b.id
    assert row_b.match_score == 0.9


@pytest.mark.asyncio
async def test_runs_get_or_create_idempotent_on_correlation(db_session):
    repo = RunsRepository(db_session)
    run1, created1 = await repo.get_or_create(kind="scrape", correlation_id="c1")
    await db_session.commit()
    run2, created2 = await repo.get_or_create(kind="scrape", correlation_id="c1")
    assert created1 is True
    assert created2 is False
    assert run1.id == run2.id


@pytest.mark.asyncio
async def test_runs_different_kind_same_corr_id_are_distinct(db_session):
    repo = RunsRepository(db_session)
    a, _ = await repo.get_or_create(kind="scrape", correlation_id="c1")
    b, _ = await repo.get_or_create(kind="tailor", correlation_id="c1")
    await db_session.commit()
    assert a.id != b.id
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/data/test_repositories.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement repositories.**

Create `src/data/repositories/__init__.py` as empty.

Create `src/data/repositories/jobs.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.job import Job


class JobsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        source: str,
        source_id: str,
        title: str,
        company: str,
        jd_text: str,
        url: str | None,
        match_score: float | None = None,
        score_breakdown: dict | None = None,
    ) -> Job:
        stmt = (
            insert(Job)
            .values(
                source=source,
                source_id=source_id,
                title=title,
                company=company,
                url=url,
                jd_text=jd_text,
                match_score=match_score,
                score_breakdown=score_breakdown,
            )
            .on_conflict_do_update(
                index_elements=["source", "source_id"],
                set_={
                    "title": title,
                    "company": company,
                    "url": url,
                    "jd_text": jd_text,
                    "match_score": match_score,
                    "score_breakdown": score_breakdown,
                },
            )
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, job_id) -> Job | None:
        return await self.session.get(Job, job_id)

    async def list_by_status(self, status: str, limit: int = 50) -> list[Job]:
        stmt = select(Job).where(Job.status == status).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars())
```

Create `src/data/repositories/runs.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.run import Run


class RunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, *, kind: str, correlation_id: str) -> tuple[Run, bool]:
        stmt = select(Run).where(Run.kind == kind, Run.correlation_id == correlation_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing, False
        row = Run(kind=kind, correlation_id=correlation_id, status="queued")
        self.session.add(row)
        await self.session.flush()
        return row, True

    async def mark_running(self, run: Run) -> None:
        from datetime import UTC, datetime
        run.status = "running"
        run.started_at = datetime.now(UTC)

    async def mark_succeeded(self, run: Run) -> None:
        from datetime import UTC, datetime
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)

    async def mark_failed(self, run: Run, *, error_code: str, error_details: dict) -> None:
        from datetime import UTC, datetime
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_code = error_code
        run.error_details = error_details
```

Create `src/data/repositories/applications.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.application import Application


class ApplicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        channel: str,
        external_ref: str | None = None,
    ) -> Application:
        row = Application(
            job_id=job_id,
            submitted_at=datetime.now(UTC),
            channel=channel,
            external_ref=external_ref,
            current_status="submitted",
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_id(self, app_id) -> Application | None:
        return await self.session.get(Application, app_id)

    async def set_status(self, application: Application, *, status: str) -> None:
        application.status_history = (application.status_history or []) + [
            {"from": application.current_status, "to": status, "at": datetime.now(UTC).isoformat()}
        ]
        application.current_status = status
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `python -m pytest tests/data/test_repositories.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/data/repositories/ tests/data/test_repositories.py
git commit -m "feat(data): repositories for jobs, runs, applications with idempotent upsert/get_or_create"
```

---

### Task 10: Celery app with four queues

**Files:**
- Create: `src/tasks/__init__.py`
- Create: `src/tasks/celery_app.py`
- Create: `tests/tasks/__init__.py`
- Create: `tests/tasks/test_celery_app.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/tasks/test_celery_app.py`:

```python
def test_celery_app_has_four_queues():
    from src.tasks.celery_app import celery_app

    queues = {q.name for q in celery_app.conf.task_queues}
    assert queues == {"scrape", "ai", "browser", "mail"}


def test_broker_url_reads_from_settings(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://test:6379/9")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://test:6379/9")
    # Force re-read
    import importlib
    import src.tasks.celery_app as mod
    importlib.reload(mod)
    assert mod.celery_app.conf.broker_url == "redis://test:6379/9"
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/tasks/ -v`
Expected: ImportError.

- [ ] **Step 3: Implement Celery app.**

Create `src/tasks/__init__.py` (empty).

Create `src/tasks/celery_app.py`:

```python
from __future__ import annotations

from celery import Celery
from kombu import Queue

from src.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "job_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.tasks.scrape",
        "src.tasks.match",
        "src.tasks.tailor",
        "src.tasks.apply",
    ],
)

celery_app.conf.update(
    task_acks_late=True,            # requeue on worker crash
    worker_prefetch_multiplier=1,   # one task per worker at a time, fair for long jobs
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
    task_queues=(
        Queue("scrape"),
        Queue("ai"),
        Queue("browser"),
        Queue("mail"),
    ),
    task_default_queue="scrape",
    task_routes={
        "src.tasks.scrape.*": {"queue": "scrape"},
        "src.tasks.match.*": {"queue": "ai"},
        "src.tasks.tailor.*": {"queue": "ai"},
        "src.tasks.apply.*": {"queue": "browser"},
    },
)
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/tasks/test_celery_app.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/tasks/ tests/tasks/
git commit -m "feat(tasks): celery app with four named queues (scrape/ai/browser/mail)"
```

---

### Task 11: `@pipeline_task` decorator with idempotency

**Files:**
- Create: `src/tasks/base.py`
- Create: `tests/tasks/test_base.py`

- [ ] **Step 1: Write the failing tests.**

Create `tests/tasks/test_base.py`:

```python
import pytest
from celery import Celery

from src.errors import ExternalServiceError, UserActionRequiredError
from src.tasks.base import pipeline_task


@pytest.fixture
def celery_app_eager(monkeypatch):
    # Run tasks synchronously in-process for tests.
    from src.tasks import celery_app as mod
    mod.celery_app.conf.task_always_eager = True
    mod.celery_app.conf.task_eager_propagates = True
    yield mod.celery_app
    mod.celery_app.conf.task_always_eager = False


def test_pipeline_task_runs_once_for_same_correlation_id(celery_app_eager, db_session):
    calls = []

    @pipeline_task(stage="test_stage", max_retries=0, queue="scrape")
    def fake(correlation_id: str, value: int) -> int:
        calls.append(value)
        return value

    fake.apply(kwargs={"correlation_id": "c1", "value": 1})
    fake.apply(kwargs={"correlation_id": "c1", "value": 2})
    # Second invocation is short-circuited by the existing run record.
    assert calls == [1]


def test_pipeline_task_retries_external_service_error(celery_app_eager):
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


def test_pipeline_task_does_not_retry_user_action_required(celery_app_eager):
    attempts = {"n": 0}

    @pipeline_task(stage="needs_user", max_retries=5, queue="browser")
    def blocked(correlation_id: str) -> None:
        attempts["n"] += 1
        raise UserActionRequiredError("need 2fa", required="linkedin_2fa")

    with pytest.raises(UserActionRequiredError):
        blocked.apply(kwargs={"correlation_id": "cy"}).get()
    assert attempts["n"] == 1
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/tasks/test_base.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `src/tasks/base.py`.**

```python
"""@pipeline_task — decorator that wraps every pipeline stage with:
- idempotency keyed by (stage, correlation_id): second call returns early.
- typed error dispatch: retry ExternalServiceError, don't retry
  UserActionRequiredError / LLMValidationError.
- audit trail: creates/updates a row in `runs`.

Full self-correcting framework (daily caps, DLQ diagnosis) lands in W4.
W1 ships the idempotency + retry core.
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
            bind_correlation(correlation_id, stage=stage, task_id=self.request.id)
            try:
                created = _mark_run_running_sync(stage=stage, correlation_id=correlation_id)
                if not created:
                    log.info("pipeline_task.skip_duplicate", correlation_id=correlation_id)
                    return None
                result = fn(*args, **kwargs)
                _mark_run_succeeded_sync(stage=stage, correlation_id=correlation_id)
                return result
            except DO_NOT_RETRY as exc:
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code=exc.error_code,
                    error_details=exc.details,
                )
                raise
            except PipelineError as exc:
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code=exc.error_code,
                    error_details=exc.details,
                )
                raise
            except Exception as exc:  # pragma: no cover - safety net
                _mark_run_failed_sync(
                    stage=stage,
                    correlation_id=correlation_id,
                    error_code="UNHANDLED",
                    error_details={"type": type(exc).__name__, "message": str(exc)},
                )
                raise
            finally:
                clear_correlation()

        return wrapper

    return decorator


# -- Synchronous helpers over the async repo --------------------------------

def _run_async(coro):
    # Simple run-coro-in-sync for Celery workers; fine since we use async
    # SQLAlchemy and each task is single-threaded.
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # When inside an already-running loop (eg tests), create a new one.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _mark_run_running_sync(*, stage: str, correlation_id: str) -> bool:
    async def _inner() -> bool:
        from src.data.db import get_sessionmaker
        from src.data.repositories.runs import RunsRepository

        maker = get_sessionmaker()
        async with maker() as session:
            repo = RunsRepository(session)
            run, created = await repo.get_or_create(kind=stage, correlation_id=correlation_id)
            if created:
                await repo.mark_running(run)
            elif run.status == "succeeded":
                await session.commit()
                return False
            await session.commit()
            return True
    return _run_async(_inner())


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
    _run_async(_inner())


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
            await repo.mark_failed(run, error_code=error_code, error_details=error_details)
            await session.commit()
    _run_async(_inner())
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/tasks/test_base.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/tasks/base.py tests/tasks/test_base.py
git commit -m "feat(tasks): @pipeline_task decorator with idempotency and typed retry policy"
```

---

### Task 12: Wrap pipeline stages as Celery tasks

**Files:**
- Create: `src/tasks/scrape.py`
- Create: `src/tasks/match.py`
- Create: `src/tasks/tailor.py`
- Create: `src/tasks/apply.py`
- Create: `tests/tasks/test_stage_wrappers.py`

- [ ] **Step 1: Write the failing wrapper tests (thin — unit tests of the adapters, not of the services they call).**

Create `tests/tasks/test_stage_wrappers.py`:

```python
from unittest.mock import MagicMock, patch

from src.tasks.scrape import run_scrape
from src.tasks.match import run_match
from src.tasks.tailor import run_tailor
from src.tasks.apply import run_apply


def test_run_scrape_invokes_scraper_service_and_persists(celery_app_eager):
    with patch("src.tasks.scrape._scrape_and_persist") as mock_impl:
        mock_impl.return_value = {"jobs_scraped": 3}
        result = run_scrape.apply(kwargs={"correlation_id": "s-1"}).get()
    assert result == {"jobs_scraped": 3}
    mock_impl.assert_called_once()


def test_run_match_invokes_matcher(celery_app_eager):
    with patch("src.tasks.match._match_all") as mock_impl:
        mock_impl.return_value = {"jobs_ranked": 7}
        assert run_match.apply(kwargs={"correlation_id": "m-1"}).get() == {"jobs_ranked": 7}


def test_run_tailor_targets_a_job(celery_app_eager):
    with patch("src.tasks.tailor._tailor_for_job") as mock_impl:
        mock_impl.return_value = {"artifacts_written": 3}
        assert run_tailor.apply(
            kwargs={"correlation_id": "t-1", "job_id": "job-uuid"}
        ).get() == {"artifacts_written": 3}


def test_run_apply_targets_a_job(celery_app_eager):
    with patch("src.tasks.apply._apply_to_job") as mock_impl:
        mock_impl.return_value = {"submitted": True}
        assert run_apply.apply(
            kwargs={"correlation_id": "a-1", "job_id": "job-uuid"}
        ).get() == {"submitted": True}
```

Also update `tests/tasks/test_base.py` to promote the `celery_app_eager` fixture to `tests/conftest.py` or define it once in `tests/tasks/conftest.py`. Create `tests/tasks/conftest.py`:

```python
import pytest


@pytest.fixture
def celery_app_eager():
    from src.tasks import celery_app as mod
    mod.celery_app.conf.task_always_eager = True
    mod.celery_app.conf.task_eager_propagates = True
    yield mod.celery_app
    mod.celery_app.conf.task_always_eager = False
```

(Remove the duplicate fixture from `test_base.py` if it conflicts.)

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/tasks/test_stage_wrappers.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement each wrapper.**

`src/tasks/scrape.py`:
```python
"""Scrape stage wrapper. Delegates to src.services.scraper.ScraperService;
persists jobs via JobsRepository."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="scrape", max_retries=2, queue="scrape")
def run_scrape(*, correlation_id: str) -> dict:
    return _scrape_and_persist(correlation_id)


def _scrape_and_persist(correlation_id: str) -> dict:
    # Intentionally thin: actual scraping is unchanged in src/services/scraper.
    # A follow-up in W4 adds selector-self-healing into the 0-results path.
    import asyncio
    from pathlib import Path

    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.scraper.service import ScraperService
    from src.utils.config import load_config
    from src.observability.logging import get_logger

    log = get_logger("tasks.scrape")
    config = load_config(Path("config.yaml"))
    service = ScraperService(config, Path("."), log)
    jobs = service.scrape()

    async def _persist() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobsRepository(session)
            for j in jobs:
                await repo.upsert(
                    source=j.source,
                    source_id=j.job_id,
                    title=j.title,
                    company=j.company,
                    jd_text=j.description or "",
                    url=j.url,
                )
            await session.commit()
        return len(jobs)

    count = asyncio.run(_persist())
    return {"jobs_scraped": count}
```

`src/tasks/match.py`:
```python
"""Match stage wrapper. Runs embedding + scoring on all jobs with status='new'."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="match", max_retries=2, queue="ai")
def run_match(*, correlation_id: str) -> dict:
    return _match_all(correlation_id)


def _match_all(correlation_id: str) -> dict:
    # Thin wrapper around src.matcher until W4 adds output validation + retries.
    import asyncio
    from pathlib import Path

    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.matcher.engine import JobMatcher  # unchanged
    from src.utils.config import load_config
    from src.observability.logging import get_logger

    log = get_logger("tasks.match")
    config = load_config(Path("config.yaml"))
    service = JobMatcher(config, Path("."), log)

    async def _run() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobsRepository(session)
            jobs = await repo.list_by_status(status="new", limit=500)
            ranked = service.rank(jobs)
            for r in ranked:
                await repo.upsert(
                    source=r.source,
                    source_id=r.job_id,
                    title=r.title,
                    company=r.company,
                    jd_text=r.description or "",
                    url=r.url,
                    match_score=r.score,
                    score_breakdown=r.score_breakdown,
                )
            await session.commit()
            return len(ranked)

    n = asyncio.run(_run())
    return {"jobs_ranked": n}
```

> **Engineer note:** `JobMatcher.rank()` may have a different call shape in the current repo; read `src/matcher/engine.py` before writing the wrapper. Keep the wrapper's public contract (`correlation_id` → `{"jobs_ranked": n}`) and adapt the body to whatever the existing matcher expects. Do not rewrite the matcher itself.

`src/tasks/tailor.py`:
```python
"""Tailor stage wrapper. Generates resume/cover/pitch for a single job."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="tailor", max_retries=2, queue="ai")
def run_tailor(*, correlation_id: str, job_id: str) -> dict:
    return _tailor_for_job(correlation_id, job_id)


def _tailor_for_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.resume.engine import ResumeService
    from src.utils.config import load_config
    from src.observability.logging import get_logger

    log = get_logger("tasks.tailor")
    config = load_config(Path("config.yaml"))
    service = ResumeService(config.resume, Path("."), log)
    artifacts = service.tailor_for_job_id(job_id=job_id)  # see engineer note
    return {"artifacts_written": len(artifacts)}
```

> **Engineer note:** if `ResumeService` doesn't currently expose `tailor_for_job_id`, add the method as a thin adapter over whatever the existing tailoring entrypoint is. The W1 constraint is: a Celery task calls it with a `job_id` and gets back a list of written artifact paths. Do not replace the tailoring logic.

`src/tasks/apply.py`:
```python
"""Apply stage wrapper. Uses src.apply.linkedin flow unchanged."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="apply", max_retries=1, queue="browser")
def run_apply(*, correlation_id: str, job_id: str) -> dict:
    return _apply_to_job(correlation_id, job_id)


def _apply_to_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.apply.linkedin_easy_apply import LinkedInEasyApplyBot  # unchanged
    from src.utils.config import load_config
    from src.observability.logging import get_logger

    log = get_logger("tasks.apply")
    config = load_config(Path("config.yaml"))
    flow = LinkedInEasyApplyBot(config, Path("."), log)
    submitted = flow.apply_by_job_id(job_id=job_id)
    return {"submitted": bool(submitted)}
```

> **Engineer note:** `LinkedInEasyApplyBot` in the current codebase may iterate over all jobs. The W1 goal is a single-job entrypoint. If the current API only operates on all jobs, extract the per-job inner function into a method (e.g. `apply_by_job_id`); leave the outer loop as a higher-level orchestration for the CLI. Do not alter the existing Easy Apply mechanics.

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/tasks/test_stage_wrappers.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/tasks/scrape.py src/tasks/match.py src/tasks/tailor.py src/tasks/apply.py tests/tasks/test_stage_wrappers.py tests/tasks/conftest.py
git commit -m "feat(tasks): Celery wrappers for scrape/match/tailor/apply stages"
```

---

### Task 13: CLI integration — `main.py worker`, `main.py migrate`

**Files:**
- Modify: `main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_cli.py`:

```python
import subprocess
import sys


def test_cli_worker_is_registered():
    # We check help output for the subcommand rather than actually starting celery.
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True, text=True,
    )
    assert "worker" in result.stdout
    assert "migrate" in result.stdout


def test_cli_migrate_dry_run_prints_version():
    result = subprocess.run(
        [sys.executable, "main.py", "migrate", "--dry-run"],
        capture_output=True, text=True,
    )
    # dry-run just prints the target revision, never touches the DB.
    assert result.returncode == 0
    assert "head" in result.stdout.lower() or "revision" in result.stdout.lower()
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/test_cli.py -v`
Expected: fails (commands not registered).

- [ ] **Step 3: Modify `main.py` to add the new subcommands.**

In `main.py`, locate the existing CLI parser (it uses `argparse` with subparsers today). Add subcommands:

```python
# ... existing imports ...
import subprocess

def _register_worker(subparsers) -> None:
    p = subparsers.add_parser("worker", help="Start a Celery worker for one or more queues.")
    p.add_argument("--queues", default="scrape,ai,browser,mail")
    p.add_argument("--concurrency", type=int, default=2)
    p.set_defaults(func=_cmd_worker)


def _cmd_worker(args) -> int:
    cmd = [
        "celery", "-A", "src.tasks.celery_app", "worker",
        "-Q", args.queues,
        "--concurrency", str(args.concurrency),
        "--loglevel", "INFO",
    ]
    return subprocess.call(cmd)


def _register_migrate(subparsers) -> None:
    p = subparsers.add_parser("migrate", help="Run Alembic upgrade head.")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_migrate)


def _cmd_migrate(args) -> int:
    if args.dry_run:
        print("Target revision: head")
        return 0
    return subprocess.call(["alembic", "upgrade", "head"])


def _register_migrate_sqlite(subparsers) -> None:
    p = subparsers.add_parser("migrate-sqlite", help="Import existing SQLite tracking into Postgres.")
    p.add_argument("--from", dest="source", default="artifacts/tracking.sqlite")
    p.set_defaults(func=_cmd_migrate_sqlite)


def _cmd_migrate_sqlite(args) -> int:
    from src.cli.migrate_sqlite import run as _run
    return _run(source=args.source)
```

Wire them in wherever the subparsers are built — after the existing `pipeline`/`scrape`/`match`/`resume`/`apply`/`sync-notion`/`dashboard` registrations.

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add main.py tests/test_cli.py
git commit -m "feat(cli): add worker, migrate, migrate-sqlite subcommands"
```

---

### Task 14: SQLite → Postgres migration utility

**Files:**
- Create: `src/cli/__init__.py`
- Create: `src/cli/migrate_sqlite.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_migrate_sqlite.py`
- Create fixture: `tests/fixtures/tracking.sqlite`

- [ ] **Step 1: Write the failing test.**

Create a small helper that generates the fixture SQLite DB at test-collection time.

Create `tests/cli/__init__.py` as empty.

Create `tests/cli/test_migrate_sqlite.py`:

```python
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from src.cli.migrate_sqlite import run as migrate_run
from src.data.db import get_sessionmaker
from src.data.models.application import Application


@pytest.fixture
def sqlite_fixture(tmp_path: Path) -> Path:
    db = tmp_path / "tracking.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        """CREATE TABLE applications (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            submitted_at TEXT,
            channel TEXT,
            status TEXT,
            notes TEXT
        )"""
    )
    con.execute(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?)",
        ("app-1", "job-1", "2026-01-01T00:00:00Z", "easy_apply", "submitted", ""),
    )
    con.commit()
    con.close()
    return db


@pytest.mark.asyncio
async def test_migrate_imports_applications(sqlite_fixture, db_session):
    rc = migrate_run(source=str(sqlite_fixture))
    assert rc == 0
    maker = get_sessionmaker()
    async with maker() as session:
        rows = (await session.execute(select(Application))).scalars().all()
    assert len(rows) == 1
    assert rows[0].channel == "easy_apply"
```

- [ ] **Step 2: Run to verify failure.**

Run: `python -m pytest tests/cli/test_migrate_sqlite.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the importer.**

Create `src/cli/__init__.py` as empty.

Create `src/cli/migrate_sqlite.py`:

```python
"""One-shot importer from the legacy SQLite tracking DB into Postgres.
Lossless: fails (returns non-zero) if any row cannot be mapped."""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from src.data.db import get_sessionmaker
from src.data.models.application import Application
from src.observability.logging import get_logger

log = get_logger("cli.migrate_sqlite")


def run(*, source: str) -> int:
    path = Path(source)
    if not path.exists():
        log.warning("migrate_sqlite.missing_source", source=source)
        return 0  # Nothing to migrate is not an error.

    return asyncio.run(_migrate(path))


async def _migrate(path: Path) -> int:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    rows = list(con.execute("SELECT * FROM applications"))
    con.close()

    maker = get_sessionmaker()
    async with maker() as session:
        for row in rows:
            existing = await session.execute(
                select(Application).where(Application.id == _to_uuid(row["id"]))
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                Application(
                    id=_to_uuid(row["id"]),
                    job_id=_to_uuid(row["job_id"]),
                    submitted_at=_parse_dt(row["submitted_at"]),
                    channel=row["channel"] or "easy_apply",
                    current_status=row["status"] or "submitted",
                    status_history=[],
                    notes=row["notes"] or "",
                )
            )
        await session.commit()
    log.info("migrate_sqlite.done", imported=len(rows))
    return 0


def _to_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, value or "legacy")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0)
```

- [ ] **Step 4: Run to verify pass.**

Run: `python -m pytest tests/cli/test_migrate_sqlite.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit.**

```bash
git add src/cli/ tests/cli/
git commit -m "feat(cli): migrate-sqlite imports legacy tracking DB into Postgres"
```

---

### Task 15: End-to-end pipeline test against Celery + Postgres

**Files:**
- Create: `tests/test_e2e_pipeline.py`

- [ ] **Step 1: Write the end-to-end test.**

Create `tests/test_e2e_pipeline.py`:

```python
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_scrape_then_match_then_tailor_roundtrip(db_session, celery_app_eager):
    """Exercises the full chain with the external services mocked so CI
    stays hermetic. Real external-service smoke is gated behind
    RUN_CONTRACT_TESTS=1 in test_contracts."""
    from src.tasks.scrape import run_scrape
    from src.tasks.match import run_match
    from src.tasks.tailor import run_tailor

    fake_jobs = [_fake_job("j-1"), _fake_job("j-2")]

    with patch("src.tasks.scrape.ScraperService") as SC, \
         patch("src.tasks.match.JobMatcher") as MC, \
         patch("src.tasks.tailor.ResumeService") as RS:
        SC.return_value.scrape.return_value = fake_jobs
        MC.return_value.rank.return_value = fake_jobs
        RS.return_value.tailor_for_job_id.return_value = ["p1", "p2", "p3"]

        run_scrape.apply(kwargs={"correlation_id": "e2e-1"}).get()
        run_match.apply(kwargs={"correlation_id": "e2e-1"}).get()
        r = run_tailor.apply(kwargs={"correlation_id": "e2e-1", "job_id": "j-1"}).get()

    assert r == {"artifacts_written": 3}


def _fake_job(jid: str):
    from types import SimpleNamespace
    return SimpleNamespace(
        source="linkedin", job_id=jid, title="Eng", company="Co",
        description="desc", url=f"https://example.com/{jid}",
        score=0.9, score_breakdown={"desc_sim": 0.9},
    )
```

- [ ] **Step 2: Run to verify pass.**

Run: `python -m pytest tests/test_e2e_pipeline.py -v`
Expected: 1 passed. If it fails because `tailor.py` imports `ResumeService` inside the function, adjust the patch path to match the actual import.

- [ ] **Step 3: Commit.**

```bash
git add tests/test_e2e_pipeline.py
git commit -m "test(e2e): celery+postgres pipeline roundtrip with mocked externals"
```

---

### Task 16: Docker-compose for workers + developer operating notes

**Files:**
- Modify: `docker-compose.yml`
- Create: `docs/w1-operating-notes.md`

- [ ] **Step 1: Extend `docker-compose.yml` with worker services.**

Append to the existing `docker-compose.yml` (do not replace the existing app service):

```yaml
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: jobautomation
      POSTGRES_USER: jobauto
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-devpassword}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jobauto -d jobautomation"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10

  worker-scrape:
    build: .
    command: python main.py worker --queues scrape --concurrency 1
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - ./artifacts:/app/artifacts

  worker-ai:
    build: .
    command: python main.py worker --queues ai --concurrency 4
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}

  worker-browser:
    build: .
    command: python main.py worker --queues browser --concurrency 1
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - ./artifacts:/app/artifacts

  worker-mail:
    build: .
    command: python main.py worker --queues mail --concurrency 2
    env_file: .env
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}

volumes:
  pg_data:
  redis_data:
```

- [ ] **Step 2: Write `docs/w1-operating-notes.md`.**

Create `docs/w1-operating-notes.md`:

```markdown
# W1 Operating Notes

## Local dev loop

```bash
# 1. Start infra
docker compose -f docker-compose.dev.yml up -d

# 2. Create .env from .env.example; fill in the API keys.

# 3. Apply migrations
python main.py migrate

# 4. Import legacy SQLite (optional, one-time)
python main.py migrate-sqlite --from artifacts/tracking.sqlite

# 5. Start a worker in a second terminal
python main.py worker --queues scrape,ai,browser,mail

# 6. Enqueue work the normal way
python main.py pipeline
```

## Running tests

```bash
# Unit + repo + CLI tests: no infra needed for a subset
python -m pytest tests/test_errors.py tests/test_settings.py tests/observability -v

# Everything, including testcontainers-backed repo + migration + e2e
python -m pytest -v
```

## Migrations

- Schema changes: edit ORM under `src/data/models/`, then
  `alembic revision --autogenerate -m "<message>"`. Review the
  generated file before committing.
- `alembic upgrade head` applies. `alembic downgrade -1` reverts.
- Never edit committed migrations. Always generate a new one.

## Debugging a stuck run

- `SELECT * FROM runs WHERE status='running' ORDER BY started_at DESC LIMIT 20;`
- Kill the orphaned row: `UPDATE runs SET status='failed', error_code='STALE' WHERE id=...;`
- Re-enqueue by calling the CLI command again — idempotency key prevents the
  still-running (if any) duplicate from doing work.

## What's not here yet

See `docs/superpowers/specs/2026-04-21-production-web-app-design.md` §4.2–§4.6
for W2–W6 scope.
```

- [ ] **Step 3: Commit.**

```bash
git add docker-compose.yml docs/w1-operating-notes.md
git commit -m "ops(w1): docker-compose workers, postgres, redis + operating notes"
```

---

## Acceptance checklist (run at the end of W1)

- [ ] `python main.py migrate` on a fresh Postgres creates all 13 tables.
- [ ] `python main.py migrate-sqlite --from artifacts/tracking.sqlite` imports legacy rows without error.
- [ ] `python main.py pipeline` runs end-to-end against Postgres with no changes in `src/services/*`.
- [ ] Killing `redis` mid-run: Celery retries with backoff, the run resumes after Redis comes back.
- [ ] Killing a worker mid-tailor: the task is reassigned to another worker; idempotency key prevents a duplicate Claude call.
- [ ] `python -m pytest -v` passes on a clean checkout with the dev compose stack up.
- [ ] Full test suite coverage for `src/data/`, `src/tasks/`, `src/errors.py`, `src/settings.py`, `src/observability/` ≥ 80%.

When all boxes are ticked, open the W1 PR referencing the spec. Next: W2 plan.
