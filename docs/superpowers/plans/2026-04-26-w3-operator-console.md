# W3 Operator Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-page web operator console at `https://<host>/` using vanilla HTML/CSS/JS with 7 routes (dashboard, integrations, runs, dlq, config, audit, selectors), backed by 5 new FastAPI routers (integrations, dlq, config, audit, selectors).

**Architecture:** FastAPI serves the SPA shell via a catch-all route and mounts `/static` for assets. The browser authenticates using the existing device-pairing challenge/pair flow — Web Crypto API generates an Ed25519 keypair in-browser, the user pastes the bootstrap secret from `python main.py bootstrap`, and the resulting JWT is stored in `localStorage`. All 7 routes communicate with `/api/v1/*` over `fetch`.

**Tech Stack:** FastAPI `StaticFiles` + `FileResponse`, vanilla HTML/CSS/JS (no build step), Web Crypto API (Ed25519), SQLAlchemy async repos, Redis pubsub for config-reload signal, PyYAML for server-side YAML validation. All dynamic values rendered into innerHTML are escaped via `_esc()` to prevent XSS.

**Branch:** `prod/w3-console` (already created).

---

## File Map

**New backend files:**
- `src/data/repositories/audit_logs.py` — paginated list + append
- `src/data/repositories/integrations.py` — list/get/upsert
- `src/data/repositories/selector_overrides.py` — list pending + approve/reject
- `src/data/repositories/config_versions.py` — create + list recent
- `src/api/schemas/integrations.py` — IntegrationOut
- `src/api/schemas/dlq.py` — DLQItemOut
- `src/api/schemas/config.py` — ConfigOut, ConfigUpdateRequest
- `src/api/schemas/audit.py` — AuditEntryOut
- `src/api/schemas/selectors.py` — SelectorOverrideOut
- `src/api/routers/integrations.py` — GET /api/v1/integrations
- `src/api/routers/dlq.py` — GET/POST /api/v1/dlq
- `src/api/routers/config.py` — GET/PUT /api/v1/config
- `src/api/routers/audit.py` — GET /api/v1/audit
- `src/api/routers/selectors.py` — GET/POST /api/v1/selectors
- `tests/data/repositories/test_w3_repos.py` — repo unit tests
- `tests/api/test_integrations.py`
- `tests/api/test_dlq.py`
- `tests/api/test_config.py`
- `tests/api/test_audit.py`
- `tests/api/test_selectors.py`
- `static/auth.js` — Web Crypto Ed25519 challenge/pair + JWT storage

**Modified files:**
- `src/api/app.py` — mount StaticFiles, include 5 new routers, SPA catch-all
- `static/index.html` — full SPA shell with 7 view containers
- `static/style.css` — extend with view/nav/form utilities
- `static/app.js` — client-side router + all 7 view renderers

---

## Task 0: FastAPI static file serving + SPA catch-all

**Files:**
- Modify: `src/api/app.py`
- Test: `tests/api/test_spa.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_spa.py
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_spa_root_returns_html(async_client):
    r = await async_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio(loop_scope="session")
async def test_spa_subroute_returns_html(async_client):
    r = await async_client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio(loop_scope="session")
async def test_static_css_served(async_client):
    r = await async_client.get("/static/style.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_spa.py -v
```
Expected: all 3 FAIL (`404 Not Found`)

- [ ] **Step 3: Update `src/api/app.py`**

Add static file mounting and SPA catch-all. The catch-all must be the very last route registered so all `/api/v1/*` routes take priority.

```python
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Job Automation AI",
        version=settings.app_version,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(IdempotencyMiddleware)

    import pathlib
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    _static = pathlib.Path("static")
    if _static.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/v1/status")
    async def status(_device=Depends(get_current_device)):
        from src.api.core.redis_dep import get_redis
        redis = get_redis()
        info = await redis.info("server")
        return {"redis_version": info.get("redis_version"), "status": "ok"}

    app.include_router(auth_router,         prefix="/api/v1/auth",         tags=["auth"])
    app.include_router(devices_router,      prefix="/api/v1/devices",      tags=["devices"])
    app.include_router(jobs_router,         prefix="/api/v1/jobs",         tags=["jobs"])
    app.include_router(runs_router,         prefix="/api/v1/runs",         tags=["runs"])
    app.include_router(applications_router, prefix="/api/v1/applications", tags=["applications"])
    app.include_router(pipeline_router,     prefix="/api/v1/pipeline",     tags=["pipeline"])
    app.include_router(ws_router,           prefix="/api/v1",              tags=["ws"])

    # SPA catch-all — MUST be last so all /api/v1/* routes match first
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str):
        index = _static / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Operator console not yet deployed"}

    return app
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/api/test_spa.py -v
```
Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/app.py tests/api/test_spa.py
git commit -m "feat(api): mount StaticFiles + SPA catch-all route"
```

---

## Task 1: Four new repositories

**Files:**
- Create: `src/data/repositories/audit_logs.py`
- Create: `src/data/repositories/integrations.py`
- Create: `src/data/repositories/selector_overrides.py`
- Create: `src/data/repositories/config_versions.py`
- Test: `tests/data/repositories/test_w3_repos.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/repositories/test_w3_repos.py
import uuid
import pytest
import pytest_asyncio


# ── AuditLog ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_append_and_list(db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    repo = AuditLogRepository(db_session)
    entry = await repo.append(actor="device-1", action="config.update", target="config.yaml")
    assert entry.id is not None

    items, total = await repo.list_paginated(page=1, per_page=10)
    assert total >= 1
    assert any(e.action == "config.update" for e in items)


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_filter_by_actor(db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    repo = AuditLogRepository(db_session)
    await repo.append(actor="unique-actor-xyz", action="test.action", target="t")
    items, total = await repo.list_paginated(actor="unique-actor-xyz")
    assert total >= 1
    assert all(e.actor == "unique-actor-xyz" for e in items)


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_upsert_and_list(db_session):
    from src.data.repositories.integrations import IntegrationsRepository
    repo = IntegrationsRepository(db_session)

    row = await repo.upsert(provider="test_gmail", status="connected")
    assert row.provider == "test_gmail"

    all_rows = await repo.list_all()
    assert any(r.provider == "test_gmail" for r in all_rows)


@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_upsert_updates_existing(db_session):
    from src.data.repositories.integrations import IntegrationsRepository
    repo = IntegrationsRepository(db_session)
    await repo.upsert(provider="test_prov", status="connected")
    updated = await repo.upsert(provider="test_prov", status="error", last_error="token expired")
    assert updated.status == "error"
    assert updated.last_error == "token expired"


# ── SelectorOverride ──────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_selector_overrides_list_pending(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    pending = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.job_card",
        selector=".new-selector",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(pending)
    await db_session.flush()

    rows = await repo.list_pending()
    assert any(r.id == pending.id for r in rows)


@pytest.mark.asyncio(loop_scope="session")
async def test_selector_override_approve(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    row = SelectorOverride(
        source="naukri",
        key_path="scraping.naukri.title",
        selector=".job-title",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.approve(row.id)
    assert updated is not None
    assert updated.status == "approved"


@pytest.mark.asyncio(loop_scope="session")
async def test_selector_override_reject(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    row = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.company",
        selector=".company-name",
        proposed_by="operator",
        status="pending",
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.reject(row.id)
    assert updated is not None
    assert updated.status == "rejected"


# ── ConfigVersion ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_config_version_create_and_list(db_session):
    from src.data.repositories.config_versions import ConfigVersionRepository
    repo = ConfigVersionRepository(db_session)

    ver = await repo.create(actor="device-abc", diff_patch="--- a/config.yaml\n+++ b/config.yaml\n")
    assert ver.id is not None

    recent = await repo.list_recent(limit=5)
    assert any(v.id == ver.id for v in recent)
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/data/repositories/test_w3_repos.py -v
```
Expected: all FAIL (`ImportError: cannot import name ...`)

- [ ] **Step 3: Create `src/data/repositories/audit_logs.py`**

```python
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        actor: str | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        if actor:
            stmt = stmt.where(AuditLog.actor == actor)
            count_stmt = count_stmt.where(AuditLog.actor == actor)
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.at.desc()).offset((page - 1) * per_page).limit(per_page)
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars())
        return items, total

    async def append(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        details: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(actor=actor, action=action, target=target, details=details)
        self.session.add(row)
        await self.session.flush()
        return row
```

- [ ] **Step 4: Create `src/data/repositories/integrations.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.integration import Integration


class IntegrationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Integration]:
        result = await self.session.execute(
            select(Integration).order_by(Integration.provider)
        )
        return list(result.scalars())

    async def get(self, provider: str) -> Integration | None:
        return await self.session.get(Integration, provider)

    async def upsert(
        self,
        *,
        provider: str,
        status: str,
        last_error: str | None = None,
    ) -> Integration:
        row = await self.get(provider)
        if row is None:
            row = Integration(provider=provider, status=status, last_error=last_error)
            self.session.add(row)
        else:
            row.status = status
            row.last_error = last_error
        await self.session.flush()
        return row
```

- [ ] **Step 5: Create `src/data/repositories/selector_overrides.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.selector_override import SelectorOverride


class SelectorOverridesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending(self) -> list[SelectorOverride]:
        stmt = (
            select(SelectorOverride)
            .where(SelectorOverride.status == "pending")
            .order_by(SelectorOverride.proposed_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars())

    async def get(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        return await self.session.get(SelectorOverride, selector_id)

    async def approve(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        row = await self.get(selector_id)
        if row is None:
            return None
        row.status = "approved"
        await self.session.flush()
        return row

    async def reject(self, selector_id: uuid.UUID) -> SelectorOverride | None:
        row = await self.get(selector_id)
        if row is None:
            return None
        row.status = "rejected"
        await self.session.flush()
        return row
```

- [ ] **Step 6: Create `src/data/repositories/config_versions.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.config_version import ConfigVersion


class ConfigVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, actor: str, diff_patch: str) -> ConfigVersion:
        row = ConfigVersion(actor=actor, diff_patch=diff_patch)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_recent(self, *, limit: int = 10) -> list[ConfigVersion]:
        stmt = (
            select(ConfigVersion)
            .order_by(ConfigVersion.applied_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/data/repositories/test_w3_repos.py -v
```
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add src/data/repositories/audit_logs.py \
        src/data/repositories/integrations.py \
        src/data/repositories/selector_overrides.py \
        src/data/repositories/config_versions.py \
        tests/data/repositories/test_w3_repos.py
git commit -m "feat(repos): AuditLog, Integration, SelectorOverride, ConfigVersion repositories"
```

---

## Task 2: W3 API schemas

**Files:**
- Create: `src/api/schemas/integrations.py`
- Create: `src/api/schemas/dlq.py`
- Create: `src/api/schemas/config.py`
- Create: `src/api/schemas/audit.py`
- Create: `src/api/schemas/selectors.py`

No separate test — schemas are exercised through router tests.

- [ ] **Step 1: Create `src/api/schemas/integrations.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class IntegrationOut(BaseModel):
    provider: str
    status: str
    last_error: str | None = None
    last_check_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create `src/api/schemas/dlq.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DLQItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    correlation_id: str
    status: str
    error_code: str | None = None
    error_details: dict | None = None
    retry_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create `src/api/schemas/config.py`**

```python
from __future__ import annotations

from pydantic import BaseModel


class ConfigOut(BaseModel):
    yaml_text: str


class ConfigUpdateRequest(BaseModel):
    yaml_text: str
```

- [ ] **Step 4: Create `src/api/schemas/audit.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    actor: str
    action: str
    target: str
    details: dict | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create `src/api/schemas/selectors.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SelectorOverrideOut(BaseModel):
    id: uuid.UUID
    source: str
    key_path: str
    selector: str
    proposed_at: datetime
    proposed_by: str
    status: str
    dom_snapshot_path: str | None = None
    provenance: dict | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Commit**

```bash
git add src/api/schemas/integrations.py src/api/schemas/dlq.py \
        src/api/schemas/config.py src/api/schemas/audit.py \
        src/api/schemas/selectors.py
git commit -m "feat(schemas): W3 response/request models — integrations, dlq, config, audit, selectors"
```

---

## Task 3: Integrations router

**Files:**
- Create: `src/api/routers/integrations.py`
- Test: `tests/api/test_integrations.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_integrations.py
import json
import secrets

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_list_empty(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/integrations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_requires_auth(async_client):
    r = await async_client.get("/api/v1/integrations")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_integrations.py -v
```
Expected: both FAIL (`404 Not Found`)

- [ ] **Step 3: Create `src/api/routers/integrations.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.deps import get_current_device
from src.api.schemas.integrations import IntegrationOut
from src.data.db import get_sessionmaker
from src.data.repositories.integrations import IntegrationsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = IntegrationsRepository(db)
    return await repo.list_all()
```

- [ ] **Step 4: Register in `src/api/app.py`**

Add import and `include_router` call. The integrations router must be included before the SPA catch-all. In `create_app()`:

```python
from src.api.routers.integrations import router as integrations_router
# ... (add after ws_router include, before the catch-all)
app.include_router(integrations_router, prefix="/api/v1/integrations", tags=["integrations"])
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_integrations.py -v
```
Expected: both PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/integrations.py src/api/app.py tests/api/test_integrations.py
git commit -m "feat(api): GET /api/v1/integrations"
```

---

## Task 4: DLQ router

**Files:**
- Create: `src/api/routers/dlq.py`
- Test: `tests/api/test_dlq.py`

DLQ = runs with `status = 'failed'`. Dismiss sets `status = 'dismissed'`. Retry re-enqueues the scrape task.

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_dlq.py
import json
import secrets
import uuid

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_list_empty(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/dlq",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_dismiss_run(async_client, redis_client, db_session):
    from src.data.models.run import Run
    token = await _get_token(async_client, redis_client)

    run = Run(
        kind="scrape",
        correlation_id=f"test-dlq-{uuid.uuid4()}",
        status="failed",
        error_code="scrape_failed",
        error_details={"msg": "timeout"},
    )
    db_session.add(run)
    await db_session.commit()

    r = await async_client.post(
        f"/api/v1/dlq/{run.id}/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["dismissed"] is True

    await db_session.refresh(run)
    assert run.status == "dismissed"


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_dismiss_nonexistent_returns_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        f"/api/v1/dlq/{uuid.uuid4()}/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_requires_auth(async_client):
    r = await async_client.get("/api/v1/dlq")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_dlq.py -v
```
Expected: all FAIL

- [ ] **Step 3: Create `src/api/routers/dlq.py`**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.dlq import DLQItemOut
from src.data.db import get_sessionmaker
from src.data.repositories.runs import RunsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[DLQItemOut])
async def list_dlq(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    items, total = await repo.list_paginated(page=page, per_page=per_page, status="failed")
    return PaginatedResponse(
        items=items, total=total, page=page, per_page=per_page,
        has_next=(page * per_page) < total,
    )


@router.post("/{run_id}/retry", status_code=202)
async def retry_dlq_item(
    run_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.status != "failed":
        raise HTTPException(404, detail="DLQ item not found")
    # Deferred: src.tasks.celery_app calls get_settings() at module load time
    from src.tasks.scrape import run_scrape
    run_scrape.apply_async(kwargs={"correlation_id": run.correlation_id})
    return {"queued": True}


@router.post("/{run_id}/dismiss", status_code=200)
async def dismiss_dlq_item(
    run_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = RunsRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.status != "failed":
        raise HTTPException(404, detail="DLQ item not found")
    run.status = "dismissed"
    await db.commit()
    return {"dismissed": True}
```

- [ ] **Step 4: Register in `src/api/app.py`**

```python
from src.api.routers.dlq import router as dlq_router
# ...
app.include_router(dlq_router, prefix="/api/v1/dlq", tags=["dlq"])
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_dlq.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/dlq.py src/api/app.py tests/api/test_dlq.py
git commit -m "feat(api): GET/POST /api/v1/dlq — list failed runs, retry, dismiss"
```

---

## Task 5: Config router

**Files:**
- Create: `src/api/routers/config.py`
- Test: `tests/api/test_config.py`

GET reads `config.yaml` from `settings.config_path`. PUT validates YAML, diffs, writes to disk, saves a ConfigVersion record, and publishes `events:config_reload` to Redis.

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_config.py
import json
import secrets

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_config_get_returns_yaml(async_client, redis_client, tmp_path):
    token = await _get_token(async_client, redis_client)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("scraping:\n  enabled: true\n")

    from src.settings import get_settings
    original_path = get_settings().config_path
    get_settings().config_path = str(cfg_file)
    try:
        r = await async_client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "scraping" in r.json()["yaml_text"]
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_config_put_valid_yaml(async_client, redis_client, tmp_path):
    token = await _get_token(async_client, redis_client)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("scraping:\n  enabled: true\n")

    from src.settings import get_settings
    original_path = get_settings().config_path
    get_settings().config_path = str(cfg_file)
    try:
        new_yaml = "scraping:\n  enabled: false\n  max_jobs: 50\n"
        r = await async_client.put(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            content=json.dumps({"yaml_text": new_yaml}),
        )
        assert r.status_code == 200
        assert "max_jobs" in r.json()["yaml_text"]
        assert cfg_file.read_text() == new_yaml
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_config_put_invalid_yaml_returns_400(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.put(
        "/api/v1/config",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        content=json.dumps({"yaml_text": "key: [unclosed bracket"}),
    )
    assert r.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_config_requires_auth(async_client):
    r = await async_client.get("/api/v1/config")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_config.py -v
```
Expected: all FAIL

- [ ] **Step 3: Create `src/api/routers/config.py`**

```python
from __future__ import annotations

import pathlib
from difflib import unified_diff

import yaml
from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.core.redis_dep import get_redis
from src.api.schemas.config import ConfigOut, ConfigUpdateRequest
from src.data.db import get_sessionmaker
from src.data.repositories.config_versions import ConfigVersionRepository
from src.settings import get_settings

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=ConfigOut)
async def get_config(_device=Depends(get_current_device)):
    config_path = pathlib.Path(get_settings().config_path)
    yaml_text = config_path.read_text() if config_path.exists() else ""
    return ConfigOut(yaml_text=yaml_text)


@router.put("", response_model=ConfigOut)
async def update_config(
    body: ConfigUpdateRequest,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
    redis=Depends(get_redis),
):
    try:
        yaml.safe_load(body.yaml_text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}")

    config_path = pathlib.Path(get_settings().config_path)
    old_text = config_path.read_text() if config_path.exists() else ""

    diff = "".join(
        unified_diff(
            old_text.splitlines(keepends=True),
            body.yaml_text.splitlines(keepends=True),
            fromfile="config.yaml",
            tofile="config.yaml",
        )
    )

    config_path.write_text(body.yaml_text)

    repo = ConfigVersionRepository(db)
    await repo.create(actor=str(_device.id), diff_patch=diff)
    await db.commit()

    await redis.publish("events:config_reload", "{}")
    return ConfigOut(yaml_text=body.yaml_text)
```

- [ ] **Step 4: Register in `src/api/app.py`**

```python
from src.api.routers.config import router as config_router
# ...
app.include_router(config_router, prefix="/api/v1/config", tags=["config"])
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_config.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/config.py src/api/app.py tests/api/test_config.py
git commit -m "feat(api): GET/PUT /api/v1/config — YAML validation, diff, ConfigVersion, reload event"
```

---

## Task 6: Audit router

**Files:**
- Create: `src/api/routers/audit.py`
- Test: `tests/api/test_audit.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_audit.py
import json
import secrets

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_list_paginated(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_filter_by_action(async_client, redis_client, db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    token = await _get_token(async_client, redis_client)

    repo = AuditLogRepository(db_session)
    await repo.append(actor="test-device", action="unique.action.xyz", target="target")
    await db_session.commit()

    r = await async_client.get(
        "/api/v1/audit?action=unique.action.xyz",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert all(item["action"] == "unique.action.xyz" for item in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_requires_auth(async_client):
    r = await async_client.get("/api/v1/audit")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_audit.py -v
```
Expected: all FAIL

- [ ] **Step 3: Create `src/api/routers/audit.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.core.deps import get_current_device
from src.api.schemas.audit import AuditEntryOut
from src.api.schemas.common import PaginatedResponse
from src.data.db import get_sessionmaker
from src.data.repositories.audit_logs import AuditLogRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[AuditEntryOut])
async def list_audit(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    actor: str | None = Query(None),
    action: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = AuditLogRepository(db)
    items, total = await repo.list_paginated(
        page=page, per_page=per_page, actor=actor, action=action
    )
    return PaginatedResponse(
        items=items, total=total, page=page, per_page=per_page,
        has_next=(page * per_page) < total,
    )
```

- [ ] **Step 4: Register in `src/api/app.py`**

```python
from src.api.routers.audit import router as audit_router
# ...
app.include_router(audit_router, prefix="/api/v1/audit", tags=["audit"])
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_audit.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/audit.py src/api/app.py tests/api/test_audit.py
git commit -m "feat(api): GET /api/v1/audit — paginated with actor/action filters"
```

---

## Task 7: Selectors router

**Files:**
- Create: `src/api/routers/selectors.py`
- Test: `tests/api/test_selectors.py`

Approve persists the approved selector to `config.overrides.yaml` (a sibling of `config.yaml`, keyed by `key_path`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_selectors.py
import json
import secrets
import uuid

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_list_pending(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/selectors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_approve(async_client, redis_client, db_session, tmp_path):
    from src.data.models.selector_override import SelectorOverride
    from src.settings import get_settings
    import yaml

    token = await _get_token(async_client, redis_client)

    row = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.job_card",
        selector=".new-job-card",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.commit()

    original_path = get_settings().config_path
    get_settings().config_path = str(tmp_path / "config.yaml")
    try:
        r = await async_client.post(
            f"/api/v1/selectors/{row.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        overrides_file = tmp_path / "config.overrides.yaml"
        assert overrides_file.exists()
        data = yaml.safe_load(overrides_file.read_text())
        assert data["scraping.linkedin.job_card"] == ".new-job-card"
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_reject(async_client, redis_client, db_session):
    from src.data.models.selector_override import SelectorOverride
    token = await _get_token(async_client, redis_client)

    row = SelectorOverride(
        source="naukri",
        key_path="scraping.naukri.title",
        selector=".job-title-new",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.commit()

    r = await async_client.post(
        f"/api/v1/selectors/{row.id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_approve_nonexistent_returns_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        f"/api/v1/selectors/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_requires_auth(async_client):
    r = await async_client.get("/api/v1/selectors")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/api/test_selectors.py -v
```
Expected: all FAIL

- [ ] **Step 3: Create `src/api/routers/selectors.py`**

```python
from __future__ import annotations

import pathlib
import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.selectors import SelectorOverrideOut
from src.data.db import get_sessionmaker
from src.data.repositories.selector_overrides import SelectorOverridesRepository
from src.settings import get_settings

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


def _overrides_path() -> pathlib.Path:
    base = pathlib.Path(get_settings().config_path)
    return base.parent / "config.overrides.yaml"


@router.get("", response_model=list[SelectorOverrideOut])
async def list_pending_selectors(
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    return await repo.list_pending()


@router.post("/{selector_id}/approve", response_model=SelectorOverrideOut)
async def approve_selector(
    selector_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    updated = await repo.approve(selector_id)
    if updated is None:
        raise HTTPException(404, detail="Selector override not found")
    await db.commit()

    overrides_path = _overrides_path()
    existing: dict = {}
    if overrides_path.exists():
        existing = yaml.safe_load(overrides_path.read_text()) or {}
    existing[updated.key_path] = updated.selector
    overrides_path.write_text(yaml.dump(existing, default_flow_style=False))

    return updated


@router.post("/{selector_id}/reject", response_model=SelectorOverrideOut)
async def reject_selector(
    selector_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = SelectorOverridesRepository(db)
    updated = await repo.reject(selector_id)
    if updated is None:
        raise HTTPException(404, detail="Selector override not found")
    await db.commit()
    return updated
```

- [ ] **Step 4: Register in `src/api/app.py`**

```python
from src.api.routers.selectors import router as selectors_router
# ...
app.include_router(selectors_router, prefix="/api/v1/selectors", tags=["selectors"])
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_selectors.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/selectors.py src/api/app.py tests/api/test_selectors.py
git commit -m "feat(api): GET/POST /api/v1/selectors — approve persists to config.overrides.yaml"
```

---

## Task 8: Full test suite green-check

- [ ] **Step 1: Run full API test suite**

```bash
pytest tests/api/ -v -q
```
Expected: 23 original + ~20 new W3 tests pass. Pre-existing failures in `tests/test_notion_sync.py` are out of scope.

- [ ] **Step 2: Fix any failures**

Common failure modes:
- Catch-all route matched before an API route — ensure all `include_router` calls are before the `@app.get("/{full_path:path}")` decorator.
- Import-time error from `src.tasks.scrape` — use deferred import (already done in dlq router).

- [ ] **Step 3: Commit fixes**

```bash
git add -p
git commit -m "fix(api): resolve test failures from W3 router registration"
```

---

## Task 9: SPA HTML shell + CSS utilities

**Files:**
- Rewrite: `static/index.html`
- Extend: `static/style.css`

Design: Orbital Command palette — dark bg `#070a1c`, primary `#38bdf8`, fonts Space Grotesk + JetBrains Mono.

**Security note:** All dynamic content rendered via JS must go through `_esc()` (HTML entity escaping). See Task 11.

- [ ] **Step 1: Append to `static/style.css`**

```css
/* ===== W3 OPERATOR CONSOLE ===== */
.oc-shell{display:grid;grid-template-columns:220px 1fr;grid-template-rows:64px 1fr;height:100vh;overflow:hidden;background:#070a1c;color:#eef2ff;font-family:'Space Grotesk','Inter',sans-serif;background-image:radial-gradient(ellipse at 18% 8%,rgba(139,92,246,.18),transparent 55%),radial-gradient(ellipse at 85% 85%,rgba(56,189,248,.10),transparent 60%),linear-gradient(rgba(148,163,184,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.035) 1px,transparent 1px);background-size:100% 100%,100% 100%,48px 48px,48px 48px}
.oc-topbar{grid-column:2;grid-row:1;display:flex;align-items:center;padding:0 1.5rem;border-bottom:1px solid rgba(125,211,252,.12);gap:1rem}
.oc-topbar h1{font-family:'JetBrains Mono',monospace;font-size:.875rem;color:#38bdf8;letter-spacing:.1em;flex:1}
.oc-nav{grid-column:1;grid-row:1/3;border-right:1px solid rgba(125,211,252,.12);padding:1.5rem 1rem;display:flex;flex-direction:column;gap:.25rem;background:rgba(7,10,28,.65);backdrop-filter:blur(12px)}
.oc-brand{font-family:'JetBrains Mono',monospace;font-size:.75rem;color:#38bdf8;letter-spacing:.15em;padding:.5rem .75rem 1.25rem;display:flex;align-items:center;gap:.5rem}
.oc-brand .pulse{width:8px;height:8px;border-radius:50%;background:#38bdf8;box-shadow:0 0 10px #38bdf8;animation:oc-pulse 2s ease-in-out infinite}
@keyframes oc-pulse{0%,100%{opacity:1}50%{opacity:.3}}
.oc-nav a{display:flex;align-items:center;gap:.6rem;padding:.55rem .75rem;border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.8125rem;font-family:'JetBrains Mono',monospace;transition:color .15s,background .15s}
.oc-nav a:hover{color:#eef2ff;background:rgba(56,189,248,.08)}
.oc-nav a.active{color:#38bdf8;background:rgba(56,189,248,.12)}
.oc-main{grid-column:2;grid-row:2;overflow-y:auto;padding:1.5rem}
.oc-view{display:none}
.oc-view.active{display:block}
.oc-card{background:rgba(125,211,252,.06);border:1px solid rgba(125,211,252,.15);border-radius:8px;padding:1.25rem;margin-bottom:1rem}
.oc-card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem}
.oc-card-title{font-family:'JetBrains Mono',monospace;font-size:.75rem;color:#38bdf8;letter-spacing:.1em}
.oc-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin-bottom:1rem}
.oc-stat{background:rgba(125,211,252,.06);border:1px solid rgba(125,211,252,.12);border-radius:6px;padding:.75rem 1rem}
.oc-stat .label{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:#94a3b8;letter-spacing:.08em}
.oc-stat .value{font-size:1.5rem;font-weight:700;color:#eef2ff;margin-top:.25rem}
.oc-table-wrap{overflow-x:auto}
.oc-table{width:100%;border-collapse:collapse;font-size:.8125rem}
.oc-table th{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:#94a3b8;letter-spacing:.08em;text-align:left;padding:.5rem .75rem;border-bottom:1px solid rgba(125,211,252,.12)}
.oc-table td{padding:.6rem .75rem;border-bottom:1px solid rgba(125,211,252,.06);color:#cbd5e1}
.oc-table tr:hover td{background:rgba(56,189,248,.04)}
.oc-pill{display:inline-block;padding:.15rem .5rem;border-radius:999px;font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:600;letter-spacing:.05em}
.oc-pill.ok{background:rgba(94,234,212,.12);color:#5eead4}
.oc-pill.warn{background:rgba(252,163,17,.12);color:#fca311}
.oc-pill.error{background:rgba(255,67,101,.12);color:#ff4365}
.oc-pill.pending{background:rgba(139,92,246,.12);color:#a78bfa}
.oc-pill.queued{background:rgba(148,163,184,.12);color:#94a3b8}
.oc-btn{display:inline-flex;align-items:center;gap:.4rem;padding:.35rem .75rem;border-radius:5px;font-family:'JetBrains Mono',monospace;font-size:.75rem;cursor:pointer;border:1px solid;transition:opacity .15s}
.oc-btn:disabled{opacity:.4;cursor:not-allowed}
.oc-btn-primary{background:rgba(56,189,248,.12);border-color:rgba(56,189,248,.4);color:#38bdf8}
.oc-btn-primary:hover:not(:disabled){background:rgba(56,189,248,.2)}
.oc-btn-danger{background:rgba(255,67,101,.1);border-color:rgba(255,67,101,.4);color:#ff4365}
.oc-btn-danger:hover:not(:disabled){background:rgba(255,67,101,.18)}
.oc-btn-ghost{background:transparent;border-color:rgba(148,163,184,.2);color:#94a3b8}
.oc-btn-ghost:hover:not(:disabled){border-color:rgba(148,163,184,.4);color:#eef2ff}
.oc-input{background:rgba(125,211,252,.05);border:1px solid rgba(125,211,252,.2);border-radius:5px;color:#eef2ff;padding:.5rem .75rem;font-family:'JetBrains Mono',monospace;font-size:.8rem;width:100%;box-sizing:border-box}
.oc-input:focus{outline:none;border-color:#38bdf8}
.oc-textarea{min-height:260px;resize:vertical}
.oc-label{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#94a3b8;letter-spacing:.08em;display:block;margin-bottom:.4rem}
.oc-field{margin-bottom:1rem}
.oc-diff{background:rgba(7,10,28,.8);border:1px solid rgba(125,211,252,.1);border-radius:5px;padding:.75rem 1rem;font-family:'JetBrains Mono',monospace;font-size:.75rem;overflow-x:auto;white-space:pre;color:#94a3b8;max-height:200px;overflow-y:auto}
.oc-diff .add{color:#5eead4}
.oc-diff .del{color:#ff4365}
.oc-login{display:flex;align-items:center;justify-content:center;height:100vh;background:#070a1c}
.oc-login-card{background:rgba(125,211,252,.06);border:1px solid rgba(125,211,252,.2);border-radius:12px;padding:2.5rem;width:100%;max-width:440px}
.oc-login-card h2{font-family:'JetBrains Mono',monospace;color:#38bdf8;font-size:1rem;margin-bottom:.5rem;letter-spacing:.15em}
.oc-login-card p{color:#94a3b8;font-size:.8rem;margin-bottom:1.5rem;line-height:1.5}
.oc-login-err{color:#ff4365;font-size:.8rem;font-family:'JetBrains Mono',monospace;margin-top:.75rem;display:none}
.oc-empty{color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:.8rem;padding:2rem;text-align:center}
```

- [ ] **Step 2: Rewrite `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orbital Command — Operator Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/style.css">
</head>
<body>

<div id="login-screen" class="oc-login" style="display:none">
  <div class="oc-login-card">
    <h2>ORBITAL COMMAND</h2>
    <p>Paste the bootstrap secret from <code>python main.py bootstrap</code> to pair this browser as an operator device.</p>
    <div class="oc-field">
      <label class="oc-label" for="bootstrap-input">BOOTSTRAP SECRET</label>
      <input id="bootstrap-input" class="oc-input" type="password" placeholder="32-byte hex..." autocomplete="off">
    </div>
    <button id="login-btn" class="oc-btn oc-btn-primary" style="width:100%;justify-content:center">PAIR DEVICE</button>
    <div id="login-err" class="oc-login-err"></div>
  </div>
</div>

<div id="console-shell" class="oc-shell" style="display:none">
  <nav class="oc-nav">
    <div class="oc-brand"><span class="pulse"></span>ORBITAL CMD</div>
    <a href="#/dashboard"    class="nav-link" data-route="dashboard"   ><span>⬡</span> DASHBOARD</a>
    <a href="#/integrations" class="nav-link" data-route="integrations"><span>⬡</span> INTEGRATIONS</a>
    <a href="#/runs"         class="nav-link" data-route="runs"        ><span>⬡</span> RUNS</a>
    <a href="#/dlq"          class="nav-link" data-route="dlq"         ><span>⬡</span> DLQ</a>
    <a href="#/config"       class="nav-link" data-route="config"      ><span>⬡</span> CONFIG</a>
    <a href="#/audit"        class="nav-link" data-route="audit"       ><span>⬡</span> AUDIT</a>
    <a href="#/selectors"    class="nav-link" data-route="selectors"   ><span>⬡</span> SELECTORS</a>
    <div style="flex:1"></div>
    <a href="#" id="logout-btn" class="nav-link"><span>⏻</span> LOGOUT</a>
  </nav>
  <header class="oc-topbar">
    <h1 id="view-label">DASHBOARD</h1>
    <button id="trigger-btn" class="oc-btn oc-btn-primary" style="font-size:.7rem">&#9654; TRIGGER PIPELINE</button>
  </header>
  <main class="oc-main">

    <div id="view-dashboard" class="oc-view">
      <div class="oc-stats" id="dash-stats"></div>
      <div class="oc-card">
        <div class="oc-card-header"><span class="oc-card-title">RECENT RUNS</span></div>
        <div class="oc-table-wrap"><table class="oc-table">
          <thead><tr><th>KIND</th><th>CORRELATION</th><th>STATUS</th><th>STARTED</th><th>FINISHED</th></tr></thead>
          <tbody id="dash-runs"></tbody>
        </table></div>
      </div>
    </div>

    <div id="view-integrations" class="oc-view">
      <div id="integrations-list"></div>
    </div>

    <div id="view-runs" class="oc-view">
      <div class="oc-card">
        <div class="oc-card-header">
          <span class="oc-card-title">RUNS</span>
          <select id="runs-status-filter" class="oc-input" style="width:120px;padding:.3rem .5rem">
            <option value="">ALL</option>
            <option value="queued">QUEUED</option>
            <option value="running">RUNNING</option>
            <option value="succeeded">SUCCEEDED</option>
            <option value="failed">FAILED</option>
          </select>
        </div>
        <div class="oc-table-wrap"><table class="oc-table">
          <thead><tr><th>KIND</th><th>CORRELATION</th><th>STATUS</th><th>STARTED</th><th>RETRIES</th></tr></thead>
          <tbody id="runs-list"></tbody>
        </table></div>
        <div id="runs-pagination" style="padding:.75rem 0;display:flex;gap:.5rem;justify-content:flex-end"></div>
      </div>
    </div>

    <div id="view-dlq" class="oc-view">
      <div class="oc-card">
        <div class="oc-card-header"><span class="oc-card-title">DEAD-LETTER QUEUE</span></div>
        <div class="oc-table-wrap"><table class="oc-table">
          <thead><tr><th>KIND</th><th>CORRELATION</th><th>ERROR</th><th>RETRIES</th><th>ACTIONS</th></tr></thead>
          <tbody id="dlq-list"></tbody>
        </table></div>
        <div id="dlq-pagination" style="padding:.75rem 0;display:flex;gap:.5rem;justify-content:flex-end"></div>
      </div>
    </div>

    <div id="view-config" class="oc-view">
      <div class="oc-card">
        <div class="oc-card-header"><span class="oc-card-title">CONFIG.YAML</span></div>
        <div class="oc-field">
          <textarea id="config-editor" class="oc-input oc-textarea" spellcheck="false"></textarea>
        </div>
        <div id="config-diff" class="oc-diff" style="display:none"></div>
        <div style="display:flex;gap:.5rem;margin-top:.5rem">
          <button id="config-save-btn" class="oc-btn oc-btn-primary">SAVE</button>
        </div>
        <div id="config-msg" style="margin-top:.5rem;font-family:'JetBrains Mono',monospace;font-size:.75rem"></div>
      </div>
    </div>

    <div id="view-audit" class="oc-view">
      <div class="oc-card">
        <div class="oc-card-header">
          <span class="oc-card-title">AUDIT LOG</span>
          <div style="display:flex;gap:.5rem">
            <input id="audit-actor-filter"  class="oc-input" style="width:140px;padding:.3rem .5rem" placeholder="actor...">
            <input id="audit-action-filter" class="oc-input" style="width:160px;padding:.3rem .5rem" placeholder="action...">
            <button id="audit-filter-btn" class="oc-btn oc-btn-ghost">FILTER</button>
          </div>
        </div>
        <div class="oc-table-wrap"><table class="oc-table">
          <thead><tr><th>TIME</th><th>ACTOR</th><th>ACTION</th><th>TARGET</th></tr></thead>
          <tbody id="audit-list"></tbody>
        </table></div>
        <div id="audit-pagination" style="padding:.75rem 0;display:flex;gap:.5rem;justify-content:flex-end"></div>
      </div>
    </div>

    <div id="view-selectors" class="oc-view">
      <div class="oc-card">
        <div class="oc-card-header"><span class="oc-card-title">PENDING SELECTOR PROPOSALS</span></div>
        <div id="selectors-list"></div>
      </div>
    </div>

  </main>
</div>

<script src="/static/auth.js"></script>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add static/index.html static/style.css
git commit -m "feat(console): SPA shell HTML + Orbital Command CSS utilities"
```

---

## Task 10: Auth flow (static/auth.js)

**Files:**
- Create: `static/auth.js`

Web Crypto API handles Ed25519 key generation and signing entirely in-browser. The bootstrap secret is used once; the JWT is stored in `localStorage` and used for all subsequent API calls.

- [ ] **Step 1: Create `static/auth.js`**

```javascript
/* auth.js — Web Crypto Ed25519 device-pairing + authenticated fetch */

const _JWT_KEY = 'jaa_jwt';

function getToken() {
  return localStorage.getItem(_JWT_KEY);
}

function clearToken() {
  localStorage.removeItem(_JWT_KEY);
}

function _hexToBytes(hex) {
  return new Uint8Array(hex.match(/.{2}/g).map(b => parseInt(b, 16)));
}

function _bytesToHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

function _rawToPem(raw, label) {
  const b64 = btoa(String.fromCharCode(...new Uint8Array(raw)));
  const lines = b64.match(/.{1,64}/g).join('\n');
  return `-----BEGIN ${label}-----\n${lines}\n-----END ${label}-----`;
}

async function pairDevice(bootstrapSecret) {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'Ed25519' }, true, ['sign', 'verify']
  );
  const pubRaw = await crypto.subtle.exportKey('spki', keyPair.publicKey);
  const pubPem = _rawToPem(pubRaw, 'PUBLIC KEY');

  const cr = await fetch('/api/v1/auth/challenge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bootstrap_secret: bootstrapSecret }),
  });
  if (!cr.ok) {
    const err = await cr.json().catch(() => ({}));
    throw new Error(err.detail || `Challenge failed (${cr.status})`);
  }
  const { challenge } = await cr.json();

  const sig = await crypto.subtle.sign(
    'Ed25519', keyPair.privateKey, _hexToBytes(challenge)
  );
  const sigHex = _bytesToHex(new Uint8Array(sig));

  const pr = await fetch('/api/v1/auth/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bootstrap_secret: bootstrapSecret,
      public_key: pubPem,
      signature: sigHex,
    }),
  });
  if (!pr.ok) {
    const err = await pr.json().catch(() => ({}));
    throw new Error(err.detail || `Pairing failed (${pr.status})`);
  }
  const { token } = await pr.json();
  localStorage.setItem(_JWT_KEY, token);
  return token;
}

async function authFetch(url, opts = {}) {
  const token = getToken();
  if (!token) throw Object.assign(new Error('Not authenticated'), { status: 401 });
  const headers = { ...opts.headers, Authorization: `Bearer ${token}` };
  const r = await fetch(url, { ...opts, headers });
  if (r.status === 401) {
    clearToken();
    window.location.reload();
    throw Object.assign(new Error('Session expired'), { status: 401 });
  }
  return r;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/auth.js
git commit -m "feat(console): auth.js — Web Crypto Ed25519 challenge/pair + authFetch"
```

---

## Task 11: Client-side router + all view renderers (app.js)

**Files:**
- Rewrite: `static/app.js`

All server-supplied strings rendered into HTML must go through `_esc()`. The `_statusPill()` helper is safe because it only maps known enum values to CSS class names — no user input flows through it.

- [ ] **Step 1: Rewrite `static/app.js`**

```javascript
/* app.js — hash router, view loaders, pipeline trigger */

const ROUTES = ['dashboard','integrations','runs','dlq','config','audit','selectors'];
const VIEW_LABELS = {
  dashboard:'DASHBOARD', integrations:'INTEGRATIONS', runs:'RUNS',
  dlq:'DEAD-LETTER QUEUE', config:'CONFIG.YAML', audit:'AUDIT LOG',
  selectors:'SELECTOR PROPOSALS',
};

// ── HTML escaping (XSS prevention) ───────────────────────────────────────────

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Router ────────────────────────────────────────────────────────────────────

function currentRoute() {
  const h = window.location.hash.replace('#/','').split('?')[0];
  return ROUTES.includes(h) ? h : 'dashboard';
}

function navigate(route) {
  if (!ROUTES.includes(route)) route = 'dashboard';
  window.location.hash = '#/' + route;
}

function _activateView(route) {
  document.querySelectorAll('.oc-view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById('view-' + route);
  if (el) el.classList.add('active');
  document.querySelectorAll('.nav-link').forEach(a =>
    a.classList.toggle('active', a.dataset.route === route)
  );
  const lbl = document.getElementById('view-label');
  if (lbl) lbl.textContent = VIEW_LABELS[route] || route.toUpperCase();
}

async function _loadRoute(route) {
  _activateView(route);
  try {
    const loaders = {
      dashboard:    loadDashboard,
      integrations: loadIntegrations,
      runs:         () => loadRuns(1),
      dlq:          () => loadDlq(1),
      config:       loadConfig,
      audit:        () => loadAudit(1),
      selectors:    loadSelectors,
    };
    if (loaders[route]) await loaders[route]();
  } catch (e) {
    if (e.status !== 401) console.error('View load error:', e);
  }
}

window.addEventListener('hashchange', () => _loadRoute(currentRoute()));

// ── Helpers ───────────────────────────────────────────────────────────────────

function _statusPill(status) {
  const cls = {
    succeeded:'ok', connected:'ok', approved:'ok',
    failed:'error', error:'error', rejected:'error',
    running:'warn', pending:'pending',
    queued:'queued', dismissed:'queued',
  }[status] || 'queued';
  return '<span class="oc-pill ' + cls + '">' + status.toUpperCase() + '</span>';
}

function _ts(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {dateStyle:'short', timeStyle:'medium'});
}

function _paginationButtons(page, hasNext, fnName) {
  const prev = page > 1 ? '<button class="oc-btn oc-btn-ghost" onclick="' + fnName + '(' + (page-1) + ')">&#8592; PREV</button>' : '';
  const next = hasNext   ? '<button class="oc-btn oc-btn-ghost" onclick="' + fnName + '(' + (page+1) + ')">NEXT &#8594;</button>' : '';
  const mid  = (prev||next) ? '<span style="color:#94a3b8;font-family:\'JetBrains Mono\',monospace;font-size:.75rem;padding:.35rem .5rem">PAGE ' + page + '</span>' : '';
  return prev + mid + next;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

async function loadDashboard() {
  const [rr, dr] = await Promise.all([
    authFetch('/api/v1/runs?per_page=10'),
    authFetch('/api/v1/dlq?per_page=1'),
  ]);
  const runs = await rr.json();
  const dlq  = await dr.json();

  document.getElementById('dash-stats').innerHTML = [
    {label:'TOTAL RUNS',    value: runs.total},
    {label:'DLQ ITEMS',     value: dlq.total,   warn: dlq.total > 0},
    {label:'LATEST STATUS', value: (runs.items[0]?.status || '—').toUpperCase()},
  ].map(s =>
    '<div class="oc-stat"><div class="label">' + s.label + '</div>' +
    '<div class="value"' + (s.warn ? ' style="color:#ff4365"' : '') + '>' + _esc(String(s.value)) + '</div></div>'
  ).join('');

  document.getElementById('dash-runs').innerHTML = runs.items.length
    ? runs.items.map(r =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(r.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(r.correlation_id.slice(0,20)) + '&#8230;</td>' +
        '<td>' + _statusPill(r.status) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.started_at)) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.finished_at)) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs yet.</td></tr>';
}

// ── Integrations ──────────────────────────────────────────────────────────────

async function loadIntegrations() {
  const r = await authFetch('/api/v1/integrations');
  const items = await r.json();
  const byProvider = Object.fromEntries(items.map(i => [i.provider, i]));

  const KNOWN = [
    {provider:'gmail',     label:'Gmail'},
    {provider:'linkedin',  label:'LinkedIn'},
    {provider:'openai',    label:'OpenAI'},
    {provider:'anthropic', label:'Anthropic'},
  ];

  document.getElementById('integrations-list').innerHTML = KNOWN.map(k => {
    const row    = byProvider[k.provider];
    const status = row?.status || 'disconnected';
    const errHtml = row?.last_error
      ? '<div style="color:#ff4365;font-size:.75rem;margin-top:.4rem;font-family:\'JetBrains Mono\',monospace">' + _esc(row.last_error) + '</div>'
      : '';
    const isKey = ['openai','anthropic'].includes(k.provider);
    const action = isKey
      ? '<input class="oc-input" id="apikey-' + k.provider + '" type="password" placeholder="sk-..." style="width:200px">' +
        '<button class="oc-btn oc-btn-ghost" style="margin-left:.5rem" onclick="saveApiKey(\'' + k.provider + '\')">SAVE</button>'
      : '<button class="oc-btn oc-btn-ghost" disabled>' + (status === 'connected' ? 'RECONNECT' : 'CONNECT') + '</button>';
    return '<div class="oc-card">' +
      '<div class="oc-card-header"><span class="oc-card-title">' + _esc(k.label.toUpperCase()) + '</span>' + _statusPill(status) + '</div>' +
      errHtml +
      '<div style="margin-top:.75rem">' + action + '</div>' +
      '</div>';
  }).join('');
}

window.saveApiKey = function(provider) {
  const input = document.getElementById('apikey-' + provider);
  if (!input || !input.value) return;
  alert('Key noted for ' + provider + '. Persistence to DB not yet wired (W4).');
  input.value = '';
};

// ── Runs ──────────────────────────────────────────────────────────────────────

window.loadRuns = async function(page) {
  page = page || 1;
  const status = document.getElementById('runs-status-filter')?.value || '';
  const qs = new URLSearchParams({page: page, per_page: 25});
  if (status) qs.set('status', status);
  const r = await authFetch('/api/v1/runs?' + qs);
  const data = await r.json();

  document.getElementById('runs-list').innerHTML = data.items.length
    ? data.items.map(r =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(r.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(r.correlation_id.slice(0,24)) + '&#8230;</td>' +
        '<td>' + _statusPill(r.status) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.started_at)) + '</td>' +
        '<td style="font-size:.75rem;text-align:right;color:#94a3b8">' + _esc(String(r.retry_count)) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs.</td></tr>';

  document.getElementById('runs-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadRuns');
};

// ── DLQ ───────────────────────────────────────────────────────────────────────

window.loadDlq = async function(page) {
  page = page || 1;
  const r = await authFetch('/api/v1/dlq?page=' + page + '&per_page=25');
  const data = await r.json();

  document.getElementById('dlq-list').innerHTML = data.items.length
    ? data.items.map(item =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(item.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(item.correlation_id.slice(0,20)) + '&#8230;</td>' +
        '<td style="font-size:.75rem;color:#ff4365">' + _esc(item.error_code || '—') + '</td>' +
        '<td style="font-size:.75rem;text-align:right;color:#94a3b8">' + _esc(String(item.retry_count)) + '</td>' +
        '<td>' +
        '<button class="oc-btn oc-btn-primary" style="font-size:.65rem;margin-right:.25rem" onclick="retryDlq(\'' + _esc(item.id) + '\')">RETRY</button>' +
        '<button class="oc-btn oc-btn-danger"  style="font-size:.65rem" onclick="dismissDlq(\'' + _esc(item.id) + '\')">DISMISS</button>' +
        '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">DLQ is empty.</td></tr>';

  document.getElementById('dlq-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadDlq');
};

window.retryDlq = async function(id) {
  const r = await authFetch('/api/v1/dlq/' + id + '/retry', {method:'POST'});
  if (r.ok) loadDlq(1); else alert('Retry failed: ' + r.status);
};

window.dismissDlq = async function(id) {
  const r = await authFetch('/api/v1/dlq/' + id + '/dismiss', {method:'POST'});
  if (r.ok) loadDlq(1); else alert('Dismiss failed: ' + r.status);
};

// ── Config ────────────────────────────────────────────────────────────────────

let _origConfig = '';

async function loadConfig() {
  const r    = await authFetch('/api/v1/config');
  const data = await r.json();
  _origConfig = data.yaml_text;
  const editor = document.getElementById('config-editor');
  if (editor) editor.value = data.yaml_text;
  const diff = document.getElementById('config-diff');
  if (diff) diff.style.display = 'none';
  const msg = document.getElementById('config-msg');
  if (msg) msg.textContent = '';
}

function _diffHtml(oldT, newT) {
  const o = oldT.split('\n');
  const n = newT.split('\n');
  const out = [];
  for (let i = 0; i < Math.max(o.length, n.length); i++) {
    if (i >= o.length)      out.push('<span class="add">+ ' + _esc(n[i]) + '</span>');
    else if (i >= n.length) out.push('<span class="del">- ' + _esc(o[i]) + '</span>');
    else if (o[i] !== n[i]) {
      out.push('<span class="del">- ' + _esc(o[i]) + '</span>');
      out.push('<span class="add">+ ' + _esc(n[i]) + '</span>');
    } else {
      out.push('  ' + _esc(o[i]));
    }
  }
  return out.join('\n');
}

document.addEventListener('DOMContentLoaded', function() {
  var editor = document.getElementById('config-editor');
  if (editor) {
    editor.addEventListener('input', function() {
      var diff = document.getElementById('config-diff');
      if (editor.value !== _origConfig) {
        diff.style.display = 'block';
        diff.innerHTML = _diffHtml(_origConfig, editor.value);
      } else {
        diff.style.display = 'none';
      }
    });
  }

  var saveBtn = document.getElementById('config-save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var yaml_text = document.getElementById('config-editor')?.value;
      var msg = document.getElementById('config-msg');
      saveBtn.disabled = true;
      try {
        var r = await authFetch('/api/v1/config', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({yaml_text: yaml_text}),
        });
        var data = await r.json();
        if (r.ok) {
          msg.style.color = '#5eead4';
          msg.textContent = 'Saved. Config reload event published.';
          _origConfig = data.yaml_text;
          document.getElementById('config-diff').style.display = 'none';
        } else {
          msg.style.color = '#ff4365';
          msg.textContent = data.detail || 'Save failed';
        }
      } catch (e) {
        msg.style.color = '#ff4365';
        msg.textContent = String(e);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }
});

// ── Audit ─────────────────────────────────────────────────────────────────────

window.loadAudit = async function(page) {
  page = page || 1;
  var actor  = document.getElementById('audit-actor-filter')?.value  || '';
  var action = document.getElementById('audit-action-filter')?.value || '';
  var qs = new URLSearchParams({page: page, per_page: 50});
  if (actor)  qs.set('actor',  actor);
  if (action) qs.set('action', action);
  var r    = await authFetch('/api/v1/audit?' + qs);
  var data = await r.json();

  document.getElementById('audit-list').innerHTML = data.items.length
    ? data.items.map(e =>
        '<tr>' +
        '<td style="font-size:.75rem;white-space:nowrap;color:#94a3b8">' + _esc(_ts(e.at)) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(e.actor) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem">' + _esc(e.action) + '</td>' +
        '<td style="font-size:.75rem;color:#94a3b8">' + _esc(e.target) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="4" class="oc-empty">No audit entries.</td></tr>';

  document.getElementById('audit-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadAudit');
};

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('audit-filter-btn');
  if (btn) btn.addEventListener('click', function() { loadAudit(1); });
});

// ── Selectors ─────────────────────────────────────────────────────────────────

async function loadSelectors() {
  var r     = await authFetch('/api/v1/selectors');
  var items = await r.json();
  var container = document.getElementById('selectors-list');

  if (!items.length) {
    container.innerHTML = '<div class="oc-empty">No pending selector proposals.</div>';
    return;
  }

  container.innerHTML = items.map(s =>
    '<div class="oc-card" id="sel-' + _esc(s.id) + '">' +
    '<div class="oc-card-header">' +
    '<span class="oc-card-title">' + _esc(s.source.toUpperCase()) + ' &mdash; ' + _esc(s.key_path) + '</span>' +
    _statusPill(s.status) +
    '</div>' +
    '<div style="font-family:\'JetBrains Mono\',monospace;font-size:.8rem;color:#5eead4;margin-bottom:.5rem">NEW: ' + _esc(s.selector) + '</div>' +
    '<div style="font-size:.75rem;color:#94a3b8;margin-bottom:.75rem">Proposed by <strong>' + _esc(s.proposed_by) + '</strong> at ' + _esc(_ts(s.proposed_at)) + '</div>' +
    '<div style="display:flex;gap:.5rem">' +
    '<button class="oc-btn oc-btn-primary" onclick="approveSelector(\'' + _esc(s.id) + '\')">APPROVE</button>' +
    '<button class="oc-btn oc-btn-danger"  onclick="rejectSelector(\'' + _esc(s.id) + '\')">REJECT</button>' +
    '</div>' +
    '</div>'
  ).join('');
}

window.approveSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/approve', {method:'POST'});
  if (r.ok) loadSelectors(); else alert('Approve failed: ' + r.status);
};

window.rejectSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/reject', {method:'POST'});
  if (r.ok) loadSelectors(); else alert('Reject failed: ' + r.status);
};

// ── Pipeline trigger ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('trigger-btn');
  if (!btn) return;
  btn.addEventListener('click', async function() {
    btn.disabled = true;
    btn.textContent = 'QUEUING…';
    try {
      var key = 'web-' + Date.now();
      var r   = await authFetch('/api/v1/pipeline/trigger', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'Idempotency-Key': key},
        body: JSON.stringify({}),
      });
      var data = await r.json();
      btn.textContent = '✓ QUEUED (' + _esc(data.correlation_id.slice(0,8)) + '…)';
      setTimeout(function() {
        btn.textContent = '▶ TRIGGER PIPELINE';
        btn.disabled = false;
      }, 4000);
    } catch (e) {
      btn.textContent = '▶ TRIGGER PIPELINE';
      btn.disabled = false;
      alert('Trigger failed: ' + e.message);
    }
  });
});

// ── Auth UI + boot ────────────────────────────────────────────────────────────

function _showLogin() {
  document.getElementById('login-screen').style.display  = 'flex';
  document.getElementById('console-shell').style.display = 'none';
}

function _showConsole() {
  document.getElementById('login-screen').style.display  = 'none';
  document.getElementById('console-shell').style.display = 'grid';
}

document.addEventListener('DOMContentLoaded', function() {
  var logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', function(e) {
      e.preventDefault();
      clearToken();
      _showLogin();
    });
  }

  var loginBtn = document.getElementById('login-btn');
  if (loginBtn) {
    loginBtn.addEventListener('click', async function() {
      var secret = document.getElementById('bootstrap-input')?.value?.trim();
      var errEl  = document.getElementById('login-err');
      if (!secret) {
        errEl.style.display = 'block';
        errEl.textContent = 'Enter the bootstrap secret.';
        return;
      }
      loginBtn.disabled = true;
      loginBtn.textContent = 'PAIRING…';
      try {
        await pairDevice(secret);
        _showConsole();
        _loadRoute(currentRoute());
      } catch (e) {
        errEl.style.display = 'block';
        errEl.textContent = e.message || 'Pairing failed.';
        loginBtn.disabled = false;
        loginBtn.textContent = 'PAIR DEVICE';
      }
    });
  }

  if (getToken()) {
    _showConsole();
    _loadRoute(currentRoute());
  } else {
    _showLogin();
  }
});

// Runs filter
document.addEventListener('DOMContentLoaded', function() {
  var f = document.getElementById('runs-status-filter');
  if (f) f.addEventListener('change', function() { loadRuns(1); });
});
```

- [ ] **Step 2: Commit**

```bash
git add static/app.js
git commit -m "feat(console): app.js — hash router + auth boot + all 7 view renderers (XSS-safe)"
```

---

## Task 12: Full test suite + smoke test

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --ignore=scratch -q
```
Expected: all tests pass. Pre-existing failures in `tests/test_notion_sync.py` are out of scope.

- [ ] **Step 2: Start server and smoke-test all routes**

```bash
python main.py serve --port 8000
```

Open each URL in browser. After pairing via `python main.py bootstrap`:
- `http://localhost:8000/` — login screen (no JWT)
- `http://localhost:8000/#/dashboard` — stats + recent runs table
- `http://localhost:8000/#/integrations` — 4 integration cards
- `http://localhost:8000/#/runs` — runs with status filter
- `http://localhost:8000/#/dlq` — empty or failed runs
- `http://localhost:8000/#/config` — config.yaml in textarea
- `http://localhost:8000/#/audit` — audit log
- `http://localhost:8000/#/selectors` — pending proposals

All routes must load in < 500ms on LAN. No 404s in the network tab.

- [ ] **Step 3: Fix any issues found during smoke test and commit**

```bash
git add -p
git commit -m "fix(console): address smoke test issues"
```

---

## Spec Coverage Summary

| Requirement | Tasks |
|---|---|
| Vanilla HTML/CSS/JS, no build step | 9–11 |
| Route `/` — dashboard | 9, 11 |
| Route `/integrations` | 3, 9, 11 |
| Route `/runs` | 9, 11 |
| Route `/dlq` | 4, 9, 11 |
| Route `/config` — YAML editor + diff + save | 5, 9, 11 |
| Route `/audit` | 6, 9, 11 |
| Route `/selectors` — approve → config.overrides.yaml | 7, 9, 11 |
| Orbital Command design | 9 |
| Routes load < 500ms | 12 smoke test |
| Config save publishes Redis reload event | 5 |
| Selector approve persists to config.overrides.yaml | 7 |
| Auth: Ed25519 key gen in browser (Web Crypto API) | 10 |

**Deferred:**
- Gmail full OAuth (limited-device flow) — W5
- API key persistence to encrypted DB column — W4
- Config validate-without-save endpoint — future task
- WebAuthn device pairing alternative — future hardening
