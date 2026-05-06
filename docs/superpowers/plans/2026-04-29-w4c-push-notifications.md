# W4c: Push Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push real-time notifications to the operator's phone (Android/FCM) and browser (ntfy.sh fallback) when pipeline events fire — new jobs found, apply complete, email classified. The operator can register their FCM token via the API; the pipeline's Celery tasks publish pushes after each significant event.

**Architecture:** `src/notifications/push.py` implements a `PushService` with two backends: FCM (via Google's HTTP v1 API using `google-auth` for token generation) and ntfy.sh (plain HTTP POST — no signup required, useful for quick testing). `FcmTokensRepository` provides CRUD over the existing `fcm_tokens` table. A FastAPI router at `/api/v1/notifications` handles FCM token registration from devices. The pipeline `base.py` task decorator calls `PushService.send_event()` after stage completion. Settings gains FCM project ID and ntfy topic URL fields.

**Tech Stack:** `google-auth` (already installed), `httpx` (already installed), `firebase-admin` NOT needed (we call FCM v1 HTTP API directly). No new dependencies.

---

## File Map

**New files:**
- `src/notifications/__init__.py`
- `src/notifications/push.py` — `PushService`, `PushEvent`, FCM + ntfy backends
- `src/data/repositories/fcm_tokens.py` — `FcmTokensRepository`
- `src/api/schemas/notifications.py` — request/response schemas
- `src/api/routers/notifications.py` — register/unregister FCM token
- `tests/notifications/__init__.py`
- `tests/notifications/test_push.py`
- `tests/api/test_notifications.py`

**Modified files:**
- `src/settings.py` — add `fcm_project_id`, `fcm_service_account_json`, `ntfy_topic_url`
- `src/api/app.py` — include notifications router
- `src/tasks/base.py` — fire push on pipeline stage completion

---

## Task 0: Settings fields for push backends

**Files:**
- Modify: `src/settings.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_settings.py
def test_push_notification_settings_defaults():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
        "DATABASE_URL": "postgresql+asyncpg://x/x",
        "CELERY_BROKER_URL": "redis://x", "CELERY_RESULT_BACKEND": "redis://x",
    }):
        from src.settings import Settings
        s = Settings()
        assert s.fcm_project_id is None
        assert s.fcm_service_account_json is None
        assert s.ntfy_topic_url is None
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_settings.py::test_push_notification_settings_defaults -v
```
Expected: `AttributeError: 'Settings' object has no attribute 'fcm_project_id'`

- [ ] **Step 3: Add fields to `src/settings.py`**

After the Gmail fields, add:

```python
    # Push notifications
    fcm_project_id: str | None = None
    fcm_service_account_json: str | None = None  # path to service-account JSON file
    ntfy_topic_url: str | None = None  # e.g. "https://ntfy.sh/my-job-alerts"
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_settings.py::test_push_notification_settings_defaults -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/settings.py tests/test_settings.py
git commit -m "feat(push): add push notification settings fields"
```

---

## Task 1: PushService with ntfy.sh backend

**Files:**
- Create: `src/notifications/__init__.py`
- Create: `src/notifications/push.py`
- Create: `tests/notifications/__init__.py`
- Create: `tests/notifications/test_push.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/notifications/__init__.py  (empty)
```

```python
# tests/notifications/test_push.py
from unittest.mock import MagicMock, patch
import pytest
from src.notifications.push import PushEvent, PushService


def test_push_event_fields():
    ev = PushEvent(title="Jobs found", body="3 new matches", data={"count": 3})
    assert ev.title == "Jobs found"
    assert ev.data == {"count": 3}


def test_ntfy_send_posts_to_topic_url():
    svc = PushService(ntfy_topic_url="https://ntfy.sh/test-topic")
    with patch("src.notifications.push.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        svc.send_ntfy(PushEvent(title="Test", body="Hello"))
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "https://ntfy.sh/test-topic" in str(call_kwargs)
    assert "Test" in str(call_kwargs)


def test_ntfy_skipped_when_no_topic_configured():
    svc = PushService(ntfy_topic_url=None)
    with patch("src.notifications.push.httpx.post") as mock_post:
        svc.send_ntfy(PushEvent(title="Test", body="Hello"))
    mock_post.assert_not_called()


def test_send_event_calls_available_backends(monkeypatch):
    svc = PushService(ntfy_topic_url="https://ntfy.sh/t")
    called = []
    monkeypatch.setattr(svc, "send_ntfy", lambda ev: called.append("ntfy"))
    monkeypatch.setattr(svc, "send_fcm_all", lambda ev: called.append("fcm"))
    svc.send_event(PushEvent(title="T", body="B"))
    assert "ntfy" in called
    assert "fcm" in called
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/notifications/test_push.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.notifications'`

- [ ] **Step 3: Create files**

```python
# src/notifications/__init__.py
```

```python
# src/notifications/push.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("notifications.push")


@dataclass
class PushEvent:
    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    priority: str = "default"  # "min" | "low" | "default" | "high" | "max"


class PushService:
    def __init__(
        self,
        ntfy_topic_url: str | None = None,
        fcm_project_id: str | None = None,
        fcm_service_account_json: str | None = None,
    ) -> None:
        self.ntfy_topic_url = ntfy_topic_url
        self.fcm_project_id = fcm_project_id
        self.fcm_service_account_json = fcm_service_account_json
        self._fcm_tokens: list[str] = []

    def register_fcm_token(self, token: str) -> None:
        if token not in self._fcm_tokens:
            self._fcm_tokens.append(token)

    def unregister_fcm_token(self, token: str) -> None:
        self._fcm_tokens = [t for t in self._fcm_tokens if t != token]

    def send_event(self, event: PushEvent) -> None:
        """Fire event to all configured backends. Never raises — logs errors."""
        self.send_ntfy(event)
        self.send_fcm_all(event)

    def send_ntfy(self, event: PushEvent) -> None:
        if not self.ntfy_topic_url:
            return
        try:
            resp = httpx.post(
                self.ntfy_topic_url,
                data=event.body.encode(),
                headers={
                    "Title": event.title,
                    "Priority": event.priority,
                    "Content-Type": "text/plain",
                },
                timeout=5.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.warning("ntfy push failed: %s", exc)

    def send_fcm_all(self, event: PushEvent) -> None:
        """Send to all registered FCM tokens. Skips if no tokens or no project configured."""
        if not self._fcm_tokens or not self.fcm_project_id:
            return
        for token in list(self._fcm_tokens):
            try:
                self._send_fcm_one(token, event)
            except Exception as exc:
                log.warning("FCM push to token %s... failed: %s", token[:12], exc)

    def _send_fcm_one(self, token: str, event: PushEvent) -> None:
        access_token = self._get_fcm_access_token()
        url = f"https://fcm.googleapis.com/v1/projects/{self.fcm_project_id}/messages:send"
        payload = {
            "message": {
                "token": token,
                "notification": {"title": event.title, "body": event.body},
                "data": {k: str(v) for k, v in event.data.items()},
            }
        }
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()

    def _get_fcm_access_token(self) -> str:
        import google.auth.transport.requests
        import google.oauth2.service_account

        if not self.fcm_service_account_json:
            raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON not configured")
        creds = google.oauth2.service_account.Credentials.from_service_account_file(
            self.fcm_service_account_json,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/notifications/test_push.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/notifications/__init__.py src/notifications/push.py tests/notifications/__init__.py tests/notifications/test_push.py
git commit -m "feat(push): PushService with ntfy.sh + FCM backends"
```

---

## Task 2: FcmTokensRepository

**Files:**
- Create: `src/data/repositories/fcm_tokens.py`
- Modify: `tests/notifications/test_push.py` (append repo tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/notifications/test_push.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest
from src.data.repositories.fcm_tokens import FcmTokensRepository
from src.data.models.fcm_token import FcmToken


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_register_and_list(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    token = await repo.register(device_id=device_id, token="fcm-token-abc")
    assert token.token == "fcm-token-abc"
    tokens = await repo.list_by_device(device_id)
    assert any(t.token == "fcm-token-abc" for t in tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_unregister(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    await repo.register(device_id=device_id, token="fcm-token-xyz")
    deleted = await repo.unregister(token="fcm-token-xyz")
    assert deleted is True
    tokens = await repo.list_by_device(device_id)
    assert not any(t.token == "fcm-token-xyz" for t in tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_list_all(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    await repo.register(device_id=device_id, token="fcm-t1")
    await repo.register(device_id=device_id, token="fcm-t2")
    all_tokens = await repo.list_all()
    token_strings = [t.token for t in all_tokens]
    assert "fcm-t1" in token_strings
    assert "fcm-t2" in token_strings
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/notifications/test_push.py -v -k "fcm_token"
```
Expected: `ModuleNotFoundError: No module named 'src.data.repositories.fcm_tokens'`

- [ ] **Step 3: Create `src/data/repositories/fcm_tokens.py`**

```python
# src/data/repositories/fcm_tokens.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.fcm_token import FcmToken


class FcmTokensRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, *, device_id: uuid.UUID, token: str) -> FcmToken:
        existing = await self._db.scalar(select(FcmToken).where(FcmToken.token == token))
        if existing:
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.device_id = device_id
            return existing
        row = FcmToken(
            device_id=device_id,
            token=token,
            last_seen_at=datetime.now(timezone.utc),
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def unregister(self, *, token: str) -> bool:
        result = await self._db.execute(delete(FcmToken).where(FcmToken.token == token))
        return result.rowcount > 0

    async def list_by_device(self, device_id: uuid.UUID) -> list[FcmToken]:
        rows = await self._db.scalars(select(FcmToken).where(FcmToken.device_id == device_id))
        return list(rows)

    async def list_all(self) -> list[FcmToken]:
        rows = await self._db.scalars(select(FcmToken))
        return list(rows)
```

- [ ] **Step 4: Check FcmToken is in Alembic metadata**

```bash
python -c "from src.data.models import Base; print('fcm_tokens' in Base.metadata.tables)"
```
Expected: `True`

If `False`, open `src/data/models/__init__.py` and add:
```python
from src.data.models.fcm_token import FcmToken  # noqa: F401
```

- [ ] **Step 5: Run to verify tests pass**

```bash
python -m pytest tests/notifications/test_push.py -v -k "fcm_token"
```
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/data/repositories/fcm_tokens.py tests/notifications/test_push.py
git commit -m "feat(push): FcmTokensRepository register/unregister/list"
```

---

## Task 3: Notifications API router — register/unregister FCM token

**Files:**
- Create: `src/api/schemas/notifications.py`
- Create: `src/api/routers/notifications.py`
- Modify: `src/api/app.py`
- Create: `tests/api/test_notifications.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_notifications.py
import json, secrets
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


async def _get_token(async_client, redis_client) -> str:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_register_fcm_token(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-abc-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["registered"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_unregister_fcm_token(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-to-remove"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await async_client.delete(
        "/api/v1/notifications/fcm/fcm-to-remove",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_notifications_requires_auth(async_client):
    r = await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-xyz"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/api/test_notifications.py -v
```
Expected: 3 FAIL with 404 (route not found)

- [ ] **Step 3: Create `src/api/schemas/notifications.py`**

```python
# src/api/schemas/notifications.py
from pydantic import BaseModel


class FcmRegisterRequest(BaseModel):
    fcm_token: str


class FcmRegisterOut(BaseModel):
    registered: bool


class FcmUnregisterOut(BaseModel):
    unregistered: bool
```

- [ ] **Step 4: Create `src/api/routers/notifications.py`**

```python
# src/api/routers/notifications.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.deps import get_current_device, get_db
from src.api.schemas.notifications import FcmRegisterOut, FcmRegisterRequest, FcmUnregisterOut
from src.data.repositories.fcm_tokens import FcmTokensRepository

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post("/fcm/register", response_model=FcmRegisterOut)
async def register_fcm_token(
    body: FcmRegisterRequest,
    device=Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
):
    repo = FcmTokensRepository(db)
    await repo.register(device_id=device.id, token=body.fcm_token)
    await db.commit()
    return FcmRegisterOut(registered=True)


@router.delete("/fcm/{fcm_token}", response_model=FcmUnregisterOut)
async def unregister_fcm_token(
    fcm_token: str,
    _device=Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
):
    repo = FcmTokensRepository(db)
    deleted = await repo.unregister(token=fcm_token)
    await db.commit()
    return FcmUnregisterOut(unregistered=deleted)
```

- [ ] **Step 5: Add notifications_router to `src/api/app.py`**

After the gmail router include:

```python
    from src.api.routers.notifications import router as notifications_router
    app.include_router(notifications_router)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/api/test_notifications.py -v
```
Expected: 3 PASS

- [ ] **Step 7: Run full API suite**

```bash
python -m pytest tests/api/ -q
```
Expected: `50 passed` (47 + 3 new)

- [ ] **Step 8: Commit**

```bash
git add src/api/schemas/notifications.py src/api/routers/notifications.py src/api/app.py tests/api/test_notifications.py
git commit -m "feat(push): FCM token register/unregister API endpoints"
```

---

## Task 4: Fire push notifications from pipeline task completions

**Files:**
- Modify: `src/tasks/base.py`

The `@pipeline_task` decorator wraps every Celery task. After a successful run, it should send a push notification if PushService has configured backends. We add a `_push_on_complete()` helper that creates a `PushService` from settings and fires a `PushEvent`.

- [ ] **Step 1: Write the failing test**

```python
# tests/tasks/test_push_on_complete.py
from unittest.mock import MagicMock, patch
import pytest


def test_pipeline_task_fires_push_on_success():
    push_sent = []

    with patch("src.notifications.push.httpx.post") as mock_post, \
         patch("src.tasks.base._build_push_service") as mock_svc_factory:
        mock_svc = MagicMock()
        mock_svc.send_event.side_effect = lambda ev: push_sent.append(ev.title)
        mock_svc_factory.return_value = mock_svc

        from src.tasks.base import _push_on_complete
        from src.notifications.push import PushEvent
        _push_on_complete(stage="scrape", result={"jobs_found": 5})

    assert len(push_sent) == 1
    assert "scrape" in push_sent[0].lower() or "jobs" in push_sent[0].lower()
```

Actually the decorator integration test is complex and may need a live Celery worker. Write a unit test for the helper function only:

```python
# tests/tasks/__init__.py  (create if missing — empty)
```

```python
# tests/tasks/test_push_on_complete.py
from unittest.mock import MagicMock, patch
import pytest


def test_push_on_complete_sends_event():
    mock_service = MagicMock()
    with patch("src.tasks.base._build_push_service", return_value=mock_service):
        from src.tasks.base import _push_on_complete
        _push_on_complete(stage="scrape", result={"jobs_found": 3})
    mock_service.send_event.assert_called_once()
    event = mock_service.send_event.call_args[0][0]
    assert "scrape" in event.title.lower() or "scrape" in event.body.lower()


def test_push_on_complete_never_raises():
    with patch("src.tasks.base._build_push_service", side_effect=Exception("no settings")):
        from src.tasks.base import _push_on_complete
        _push_on_complete(stage="apply", result={})  # must not raise
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/tasks/test_push_on_complete.py -v
```
Expected: `ImportError: cannot import name '_push_on_complete'`

- [ ] **Step 3: Add push helpers to `src/tasks/base.py`**

After the imports (around line 20), add:

```python
from src.notifications.push import PushEvent, PushService
```

After the `SAFE_DETAIL_KEYS` definition, add these two functions:

```python

def _build_push_service() -> PushService:
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
        svc = _build_push_service()
        body_parts = [f"Stage: {stage}"]
        for k, v in result.items():
            body_parts.append(f"{k}: {v}")
        svc.send_event(PushEvent(
            title=f"Pipeline: {stage} complete",
            body=" | ".join(body_parts[:3]),
            data=result,
        ))
    except Exception:
        log.debug("Push notification skipped (not configured or error)", exc_info=True)
```

- [ ] **Step 4: Call `_push_on_complete` inside the task wrapper**

In `src/tasks/base.py`, find the `@pipeline_task` decorator's inner wrapper where a successful result is returned (look for the `return result` after the stage function call). Add the push call just before that return:

```python
        _push_on_complete(stage=stage, result=result if isinstance(result, dict) else {})
        return result
```

The exact location depends on the decorator structure. Search for the pattern where the wrapped function is called and its result returned to Celery. If the wrapper uses `functools.wraps`, the call will look like `result = fn(*args, **kwargs)` — add `_push_on_complete(...)` on the next line.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/tasks/test_push_on_complete.py -v
```
Expected: 2 PASS

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/api/ tests/apply/ tests/gmail/ tests/notifications/ tests/tasks/ -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/tasks/base.py src/notifications/ tests/tasks/
git commit -m "feat(push): fire push notification after each pipeline stage completes"
```
