# W4b: Gmail OAuth Device-Code + Email Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Authenticate with Gmail using the OAuth 2.0 device-code flow (no browser redirect — works headlessly on a VPS), fetch unread recruiter emails, classify each as rejection/interview/offer/follow_up/other using Claude, and expose the sync + OAuth handshake through the operator console API.

**Architecture:** `src/gmail/` is a self-contained package: `oauth.py` handles device-code auth and persists the refresh token to `.gmail_token.json`; `client.py` wraps the Gmail REST API (list unread, fetch body); `classifier.py` calls Anthropic to classify a message and returns one of five statuses. A new FastAPI router at `/api/v1/gmail` exposes three endpoints: `POST /oauth/init` (returns user_code + verification_url), `GET /oauth/poll` (returns `pending`/`authorized`), and `POST /sync` (fetches + classifies unread emails, writes results to `Thread` + `Application.email_status`). The `Application` model gains a nullable `email_status` column via a new Alembic migration.

**Tech Stack:** `google-api-python-client` (already installed), `google-auth` (already installed), `anthropic` (already installed via `anthropic_api_key` in settings). New dependency: none.

---

## File Map

**New files:**
- `src/gmail/__init__.py` — package marker
- `src/gmail/oauth.py` — `GmailOAuth`: device-code init, poll, token persistence
- `src/gmail/client.py` — `GmailClient`: list unread threads, fetch message body
- `src/gmail/classifier.py` — `classify_email(subject, body, anthropic_client)` → `EmailStatus`
- `src/api/routers/gmail.py` — three endpoints
- `src/api/schemas/gmail.py` — request/response Pydantic schemas
- `src/data/migrations/versions/XXXX_add_email_status.py` — Alembic migration
- `tests/gmail/__init__.py` — package marker
- `tests/gmail/test_classifier.py` — classifier unit tests (mocked Anthropic)
- `tests/api/test_gmail.py` — API endpoint tests

**Modified files:**
- `src/data/models/application.py` — add `email_status: Mapped[str | None]`
- `src/api/app.py` — include `gmail_router`
- `src/settings.py` — add `gmail_client_id`, `gmail_client_secret`, `gmail_token_path`

---

## Task 0: Settings fields for Gmail OAuth

**Files:**
- Modify: `src/settings.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_settings.py
def test_gmail_settings_defaults():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
        "DATABASE_URL": "postgresql+asyncpg://x/x",
        "CELERY_BROKER_URL": "redis://x", "CELERY_RESULT_BACKEND": "redis://x",
    }):
        from src.settings import Settings
        s = Settings()
        assert s.gmail_client_id is None
        assert s.gmail_client_secret is None
        assert s.gmail_token_path == ".gmail_token.json"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_settings.py::test_gmail_settings_defaults -v
```
Expected: `AttributeError: 'Settings' object has no attribute 'gmail_client_id'`

- [ ] **Step 3: Add fields to `src/settings.py`**

After `linkedin_cooldown_between_apps_ms`, add:

```python
    # Gmail OAuth (device-code flow)
    gmail_client_id: str | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_token_path: str = ".gmail_token.json"
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_settings.py::test_gmail_settings_defaults -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/settings.py tests/test_settings.py
git commit -m "feat(gmail): add Gmail OAuth settings fields"
```

---

## Task 1: GmailOAuth — device-code flow + token persistence

**Files:**
- Create: `src/gmail/__init__.py`
- Create: `src/gmail/oauth.py`
- Create: `tests/gmail/__init__.py`
- Create: `tests/gmail/test_oauth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/gmail/__init__.py  (empty)
```

```python
# tests/gmail/test_oauth.py
import json, os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest
from src.gmail.oauth import GmailOAuth, DeviceCodeResponse


def _oauth(tmp_path) -> GmailOAuth:
    return GmailOAuth(
        client_id="cid",
        client_secret="csec",
        token_path=str(tmp_path / ".gmail_token.json"),
    )


def test_init_device_flow_returns_code_response(tmp_path):
    oauth = _oauth(tmp_path)
    fake_resp = {
        "device_code": "dc123",
        "user_code": "ABCD-1234",
        "verification_url": "https://google.com/device",
        "interval": 5,
        "expires_in": 1800,
    }
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = fake_resp
        mock_post.return_value.raise_for_status = MagicMock()
        result = oauth.init_device_flow()
    assert result.user_code == "ABCD-1234"
    assert result.device_code == "dc123"
    assert result.verification_url == "https://google.com/device"


def test_poll_returns_pending_on_authorization_pending(tmp_path):
    oauth = _oauth(tmp_path)
    oauth._device_code = "dc123"
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"error": "authorization_pending"}
        mock_post.return_value.raise_for_status = MagicMock()
        status = oauth.poll_for_token()
    assert status == "pending"


def test_poll_saves_token_and_returns_authorized(tmp_path):
    oauth = _oauth(tmp_path)
    oauth._device_code = "dc123"
    fake_token = {"access_token": "at", "refresh_token": "rt", "token_type": "Bearer"}
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = fake_token
        mock_post.return_value.raise_for_status = MagicMock()
        status = oauth.poll_for_token()
    assert status == "authorized"
    saved = json.loads(Path(oauth.token_path).read_text())
    assert saved["refresh_token"] == "rt"


def test_is_authorized_true_when_token_exists(tmp_path):
    oauth = _oauth(tmp_path)
    Path(oauth.token_path).write_text(json.dumps({"refresh_token": "rt", "access_token": "at"}))
    assert oauth.is_authorized() is True


def test_is_authorized_false_when_no_token(tmp_path):
    oauth = _oauth(tmp_path)
    assert oauth.is_authorized() is False
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/gmail/test_oauth.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.gmail'`

- [ ] **Step 3: Create `src/gmail/__init__.py`**

```python
# src/gmail/__init__.py
```

- [ ] **Step 4: Create `src/gmail/oauth.py`**

```python
# src/gmail/oauth.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import requests

_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass
class DeviceCodeResponse:
    device_code: str
    user_code: str
    verification_url: str
    interval: int
    expires_in: int


class GmailOAuth:
    """Device-code OAuth flow for Gmail. No browser redirect needed."""

    def __init__(self, client_id: str, client_secret: str, token_path: str = ".gmail_token.json") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = token_path
        self._device_code: str | None = None

    def init_device_flow(self) -> DeviceCodeResponse:
        """Step 1: request device + user code from Google."""
        resp = requests.post(
            _DEVICE_CODE_URL,
            data={"client_id": self.client_id, "scope": _GMAIL_SCOPE},
        )
        resp.raise_for_status()
        data = resp.json()
        self._device_code = data["device_code"]
        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_url=data["verification_url"],
            interval=data.get("interval", 5),
            expires_in=data.get("expires_in", 1800),
        )

    def poll_for_token(self) -> str:
        """Step 2: poll once. Returns 'pending' or 'authorized'. Raises on hard errors."""
        if not self._device_code:
            raise RuntimeError("Call init_device_flow() first")
        resp = requests.post(
            _TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "device_code": self._device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            if data["error"] == "authorization_pending":
                return "pending"
            if data["error"] == "slow_down":
                return "pending"
            raise RuntimeError(f"OAuth error: {data['error']}")
        Path(self.token_path).write_text(json.dumps(data))
        return "authorized"

    def is_authorized(self) -> bool:
        p = Path(self.token_path)
        if not p.exists():
            return False
        try:
            token = json.loads(p.read_text())
            return bool(token.get("refresh_token") or token.get("access_token"))
        except (json.JSONDecodeError, KeyError):
            return False

    def get_credentials(self):
        """Return a google.oauth2.credentials.Credentials object for use with the Gmail API."""
        from google.oauth2.credentials import Credentials

        token = json.loads(Path(self.token_path).read_text())
        return Credentials(
            token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            token_uri=_TOKEN_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
```

- [ ] **Step 5: Run to verify tests pass**

```bash
python -m pytest tests/gmail/test_oauth.py -v
```
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add src/gmail/__init__.py src/gmail/oauth.py tests/gmail/__init__.py tests/gmail/test_oauth.py
git commit -m "feat(gmail): GmailOAuth device-code flow + token persistence"
```

---

## Task 2: GmailClient — fetch unread threads

**Files:**
- Create: `src/gmail/client.py`
- Create: `tests/gmail/test_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/gmail/test_client.py
from unittest.mock import MagicMock, patch
import pytest
from src.gmail.client import GmailClient, EmailMessage


def _fake_service():
    svc = MagicMock()
    return svc


def test_list_unread_returns_email_messages():
    client = GmailClient(credentials=MagicMock())
    fake_list = {"messages": [{"id": "msg1"}, {"id": "msg2"}], "nextPageToken": None}
    fake_msg1 = {
        "id": "msg1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Interview invite"},
                {"name": "From", "value": "hr@example.com"},
                {"name": "Date", "value": "Mon, 28 Apr 2026 10:00:00 +0000"},
            ],
            "body": {"data": "SGkgdGhlcmU="},  # base64 "Hi there"
            "parts": [],
        },
    }
    fake_msg2 = {
        "id": "msg2",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Application received"},
                {"name": "From", "value": "no-reply@company.com"},
                {"name": "Date", "value": "Mon, 28 Apr 2026 09:00:00 +0000"},
            ],
            "body": {"data": "VGhhbmtzIQ=="},  # base64 "Thanks!"
            "parts": [],
        },
    }
    with patch("src.gmail.client.build") as mock_build:
        svc = MagicMock()
        mock_build.return_value = svc
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = fake_list
        svc.users.return_value.messages.return_value.get.return_value.execute.side_effect = [fake_msg1, fake_msg2]
        messages = client.list_unread(max_results=10)
    assert len(messages) == 2
    assert messages[0].subject == "Interview invite"
    assert messages[0].body == "Hi there"
    assert messages[1].subject == "Application received"


def test_list_unread_returns_empty_when_no_messages():
    client = GmailClient(credentials=MagicMock())
    with patch("src.gmail.client.build") as mock_build:
        svc = MagicMock()
        mock_build.return_value = svc
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {}
        messages = client.list_unread(max_results=10)
    assert messages == []
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/gmail/test_client.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.gmail.client'`

- [ ] **Step 3: Create `src/gmail/client.py`**

```python
# src/gmail/client.py
from __future__ import annotations

import base64
from dataclasses import dataclass

from googleapiclient.discovery import build


@dataclass
class EmailMessage:
    message_id: str
    subject: str
    sender: str
    date: str
    body: str


class GmailClient:
    def __init__(self, credentials) -> None:
        self._creds = credentials

    def _service(self):
        return build("gmail", "v1", credentials=self._creds)

    def list_unread(self, max_results: int = 50, query: str = "is:unread") -> list[EmailMessage]:
        svc = self._service()
        result = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        raw_messages = result.get("messages", [])
        if not raw_messages:
            return []

        emails = []
        for ref in raw_messages:
            msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            emails.append(self._parse(msg))
        return emails

    def _parse(self, msg: dict) -> EmailMessage:
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        body = self._extract_body(payload)
        return EmailMessage(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            date=headers.get("Date", ""),
            body=body,
        )

    def _extract_body(self, payload: dict) -> str:
        # Prefer plain-text part; fall back to top-level body
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return ""
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/gmail/test_client.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gmail/client.py tests/gmail/test_client.py
git commit -m "feat(gmail): GmailClient list_unread + body extraction"
```

---

## Task 3: Email classifier using Anthropic Claude

**Files:**
- Create: `src/gmail/classifier.py`
- Create: `tests/gmail/test_classifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/gmail/test_classifier.py
from unittest.mock import MagicMock, patch
import pytest
from src.gmail.classifier import classify_email, EmailStatus


def _mock_anthropic(response_text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


def test_classify_interview_request():
    client = _mock_anthropic("interview_request")
    status = classify_email(
        subject="Let's schedule a call",
        body="We'd like to invite you for an interview.",
        anthropic_client=client,
    )
    assert status == EmailStatus.INTERVIEW_REQUEST


def test_classify_rejection():
    client = _mock_anthropic("rejection")
    status = classify_email(
        subject="Your application status",
        body="We regret to inform you that we've moved forward with other candidates.",
        anthropic_client=client,
    )
    assert status == EmailStatus.REJECTION


def test_classify_offer():
    client = _mock_anthropic("offer")
    status = classify_email(
        subject="Job Offer — Senior Engineer",
        body="We are pleased to offer you the position.",
        anthropic_client=client,
    )
    assert status == EmailStatus.OFFER


def test_classify_defaults_to_other_on_unknown():
    client = _mock_anthropic("something_totally_unknown")
    status = classify_email(subject="Re: hi", body="Ok thanks", anthropic_client=client)
    assert status == EmailStatus.OTHER


def test_classify_follow_up_needed():
    client = _mock_anthropic("follow_up_needed")
    status = classify_email(
        subject="Checking in",
        body="Just wanted to see if you're still interested.",
        anthropic_client=client,
    )
    assert status == EmailStatus.FOLLOW_UP_NEEDED
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/gmail/test_classifier.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.gmail.classifier'`

- [ ] **Step 3: Create `src/gmail/classifier.py`**

```python
# src/gmail/classifier.py
from __future__ import annotations

from enum import Enum


class EmailStatus(str, Enum):
    REJECTION = "rejection"
    INTERVIEW_REQUEST = "interview_request"
    OFFER = "offer"
    FOLLOW_UP_NEEDED = "follow_up_needed"
    OTHER = "other"


_VALID_STATUSES = {s.value for s in EmailStatus}

_PROMPT = """\
Classify this recruiter email into exactly one of these categories:
  rejection, interview_request, offer, follow_up_needed, other

Reply with only the category name — no punctuation, no explanation.

Subject: {subject}

Body:
{body}"""


def classify_email(subject: str, body: str, anthropic_client) -> EmailStatus:
    """Call Claude to classify a single email. Returns EmailStatus."""
    prompt = _PROMPT.format(subject=subject[:200], body=body[:1500])
    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip().lower()
    return EmailStatus(raw) if raw in _VALID_STATUSES else EmailStatus.OTHER
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/gmail/test_classifier.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gmail/classifier.py tests/gmail/test_classifier.py
git commit -m "feat(gmail): email classifier using Claude Haiku"
```

---

## Task 4: Application.email_status column + Alembic migration

**Files:**
- Modify: `src/data/models/application.py`
- Create: `src/data/migrations/versions/XXXX_add_email_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_gmail.py  (create — we'll add more tests in Task 5)
import pytest


def test_application_model_has_email_status():
    from src.data.models.application import Application
    # Just verify the column exists on the mapped class
    assert hasattr(Application, "email_status")
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/api/test_gmail.py::test_application_model_has_email_status -v
```
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Add `email_status` to `src/data/models/application.py`**

Append after `briefing_json` line:

```python
    email_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

Full file after change:

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
    email_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 4: Generate the Alembic migration**

```bash
python -m alembic revision --autogenerate -m "add_email_status"
```

Expected: creates `src/data/migrations/versions/XXXX_add_email_status.py` with:
```python
op.add_column('applications', sa.Column('email_status', sa.String(length=32), nullable=True))
```

Verify the generated file has exactly that — autogenerate may include other noise; remove anything unrelated.

- [ ] **Step 5: Apply migration to dev DB**

```bash
python -m alembic upgrade head
```
Expected: `Running upgrade ... -> XXXX, add_email_status`

- [ ] **Step 6: Run test to verify pass**

```bash
python -m pytest tests/api/test_gmail.py::test_application_model_has_email_status -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/data/models/application.py src/data/migrations/versions/
git commit -m "feat(gmail): add email_status to Application model + migration"
```

---

## Task 5: Gmail API router — OAuth init/poll + sync

**Files:**
- Create: `src/api/schemas/gmail.py`
- Create: `src/api/routers/gmail.py`
- Modify: `src/api/app.py`
- Modify: `tests/api/test_gmail.py` (append)

- [ ] **Step 1: Write the failing API tests**

Append to `tests/api/test_gmail.py`:

```python
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_gmail_status_not_authorized(async_client, redis_client):
    import json, secrets
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub, "signature": sig,
    })
    token = r.json()["token"]

    r = await async_client.get(
        "/api/v1/gmail/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["authorized"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_gmail_init_requires_client_id(async_client, redis_client):
    import json, secrets
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub, "signature": sig,
    })
    token = r.json()["token"]

    r = await async_client.post(
        "/api/v1/gmail/oauth/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Returns 503 when GMAIL_CLIENT_ID is not set
    assert r.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_gmail_requires_auth(async_client):
    r = await async_client.get("/api/v1/gmail/status")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/api/test_gmail.py -v
```
Expected: `test_application_model_has_email_status` PASS, new tests FAIL with 404 (route not found)

- [ ] **Step 3: Create `src/api/schemas/gmail.py`**

```python
# src/api/schemas/gmail.py
from __future__ import annotations

from pydantic import BaseModel


class GmailStatusOut(BaseModel):
    authorized: bool


class OAuthInitOut(BaseModel):
    user_code: str
    verification_url: str
    expires_in: int


class OAuthPollOut(BaseModel):
    status: str  # "pending" | "authorized"


class SyncOut(BaseModel):
    processed: int
    classified: dict[str, int]  # {"rejection": 2, "interview_request": 1, ...}
```

- [ ] **Step 4: Create `src/api/routers/gmail.py`**

```python
# src/api/routers/gmail.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.gmail import GmailStatusOut, OAuthInitOut, OAuthPollOut, SyncOut
from src.settings import get_settings

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])

# In-memory device_code store keyed by device_id (single-device assumption).
# A Redis key would be used in multi-device W5; this is sufficient for now.
_pending_device_codes: dict[str, str] = {}


def _get_oauth():
    settings = get_settings()
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise HTTPException(status_code=503, detail="GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET not configured")
    from src.gmail.oauth import GmailOAuth
    return GmailOAuth(
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret.get_secret_value(),
        token_path=settings.gmail_token_path,
    )


@router.get("/status", response_model=GmailStatusOut)
async def gmail_status(_device=Depends(get_current_device)):
    settings = get_settings()
    if not settings.gmail_client_id:
        return GmailStatusOut(authorized=False)
    from src.gmail.oauth import GmailOAuth
    oauth = GmailOAuth(
        client_id=settings.gmail_client_id,
        client_secret=(settings.gmail_client_secret.get_secret_value() if settings.gmail_client_secret else ""),
        token_path=settings.gmail_token_path,
    )
    return GmailStatusOut(authorized=oauth.is_authorized())


@router.post("/oauth/init", response_model=OAuthInitOut)
async def oauth_init(device=Depends(get_current_device)):
    oauth = _get_oauth()
    code_resp = oauth.init_device_flow()
    _pending_device_codes[str(device.id)] = code_resp.device_code
    # Stash device_code back on the oauth object for poll calls
    _pending_device_codes[f"_oauth_{device.id}"] = oauth
    return OAuthInitOut(
        user_code=code_resp.user_code,
        verification_url=code_resp.verification_url,
        expires_in=code_resp.expires_in,
    )


@router.get("/oauth/poll", response_model=OAuthPollOut)
async def oauth_poll(device=Depends(get_current_device)):
    oauth = _pending_device_codes.get(f"_oauth_{device.id}")
    if not oauth:
        raise HTTPException(status_code=400, detail="No pending OAuth flow — call /oauth/init first")
    status = oauth.poll_for_token()
    if status == "authorized":
        _pending_device_codes.pop(str(device.id), None)
        _pending_device_codes.pop(f"_oauth_{device.id}", None)
    return OAuthPollOut(status=status)


@router.post("/sync", response_model=SyncOut)
async def gmail_sync(_device=Depends(get_current_device)):
    oauth = _get_oauth()
    if not oauth.is_authorized():
        raise HTTPException(status_code=403, detail="Gmail not authorized — complete OAuth flow first")

    from anthropic import Anthropic
    from src.gmail.classifier import EmailStatus, classify_email
    from src.gmail.client import GmailClient
    from src.settings import get_settings

    settings = get_settings()
    creds = oauth.get_credentials()
    client = GmailClient(credentials=creds)
    messages = client.list_unread(max_results=50)

    anthropic = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    classified: dict[str, int] = {s.value: 0 for s in EmailStatus}
    for msg in messages:
        status = classify_email(msg.subject, msg.body, anthropic)
        classified[status.value] += 1

    return SyncOut(processed=len(messages), classified=classified)
```

- [ ] **Step 5: Add gmail_router to `src/api/app.py`**

In `create_app()`, after the existing router includes, add:

```python
    from src.api.routers.gmail import router as gmail_router
    app.include_router(gmail_router)
```

- [ ] **Step 6: Run all gmail tests**

```bash
python -m pytest tests/api/test_gmail.py -v
```
Expected: 4 PASS

- [ ] **Step 7: Run full API suite**

```bash
python -m pytest tests/api/ -q
```
Expected: `47 passed` (44 existing + 3 new gmail)

- [ ] **Step 8: Commit**

```bash
git add src/gmail/ src/api/routers/gmail.py src/api/schemas/gmail.py src/api/app.py tests/api/test_gmail.py
git commit -m "feat(gmail): OAuth init/poll/sync router + API tests"
```
