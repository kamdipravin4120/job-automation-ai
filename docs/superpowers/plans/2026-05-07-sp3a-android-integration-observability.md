# SP3a: Android Integration + Pipeline Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Android companion app to the live FCM push backend, replace the Settings stub, surface `jobs_found` per run, and add DLQ management from mobile.

**Architecture:** Two parallel workstreams — (1) minimal Python backend additions (new column, schema fields, FCM token DB fix) that unlock data the app needs; (2) Android feature layers following the established MVVM + Room + Retrofit pattern from SP2. Backend tasks 1–4 are prerequisites for Android tasks 5–12.

**Tech Stack:** Python (SQLAlchemy async, Alembic, Pydantic, pytest), Kotlin (Jetpack Compose, Hilt, Room, Retrofit+Moshi, Firebase Messaging)

---

## File Map

**Backend — modified:**
- `src/data/models/run.py` — add `jobs_found: int = 0`
- `src/data/repositories/runs.py` — add `set_jobs_found(run_id, count)`
- `src/api/schemas/runs.py` — add `jobs_found`, `steps`, `error_details` to `RunOut`
- `src/tasks/scrape.py` — call `set_jobs_found()` after persisting jobs
- `src/notifications/push.py` — `send_fcm_all(event, tokens)` accepts explicit token list
- `src/tasks/base.py` — load FCM tokens from DB and pass to `send_fcm_all`

**Backend — new:**
- `src/data/migrations/versions/XXXX_add_jobs_found_to_runs.py`
- `tests/api/test_runs_sp3a.py` — new tests for RunOut fields + set_jobs_found
- `tests/notifications/test_push_sp3a.py` — FCM token DB loading test

**Android — modified:**
- `core/api/JobAiService.kt` — new DTOs (DlqDto, PaginatedRuns, PaginatedDlq, GmailStatusDto, FcmRegisterRequest), new methods (dlq list/retry/dismiss, gmailStatus, deleteDevice, registerFcmToken, getRunDetail); fix `listRuns` return type to `PaginatedRuns`; `RunDto` gains `jobsFound`, `errorCode`, `errorDetails`
- `core/db/AppDatabase.kt` — add `DlqEntity`, bump version to 3
- `auth/AuthRepository.kt` — register FCM token after successful pair
- `navigation/AppNavigation.kt` — add `Screen.Dlq`, replace Settings stub, add unpair nav
- `runs/RunsRepository.kt` — map `jobsFound`, fix paginated response, add `getRunDetail()`
- `runs/RunsViewModel.kt` — add `loadDetail(runId)`, `selectedRunId` state
- `runs/RunsScreen.kt` — `jobsFound` chip, accordion detail, DLQ badge on tab icon
- `android/app/build.gradle.kts` — firebase-messaging-ktx
- `android/app/src/main/AndroidManifest.xml` — FCM service + POST_NOTIFICATIONS permission
- `android/libs.versions.toml` — firebase-bom + messaging versions

**Android — new:**
- `android/app/google-services.json` — stub (operator must replace with real file)
- `firebase/JobAiFirebaseService.kt`
- `firebase/FcmModule.kt`
- `dlq/DlqRepository.kt`
- `dlq/DlqViewModel.kt`
- `dlq/DlqScreen.kt`
- `settings/SettingsRepository.kt`
- `settings/GmailOAuthPoller.kt`
- `settings/SettingsViewModel.kt`
- `settings/SettingsScreen.kt`

---

## Task 1: `jobs_found` on Run model + migration + `set_jobs_found()`

**Files:**
- Modify: `src/data/models/run.py`
- Modify: `src/data/repositories/runs.py`
- Create: `src/data/migrations/versions/XXXX_add_jobs_found_to_runs.py`
- Create: `tests/api/test_runs_sp3a.py`

- [ ] **Step 1: Write failing test for `set_jobs_found`**

```python
# tests/api/test_runs_sp3a.py
import uuid
import pytest
from src.data.models.run import Run
from src.data.repositories.runs import RunsRepository


@pytest.mark.asyncio(loop_scope="session")
async def test_set_jobs_found(db_session):
    run = Run(kind="scrape", correlation_id=str(uuid.uuid4()), status="succeeded")
    db_session.add(run)
    await db_session.flush()
    repo = RunsRepository(db_session)
    await repo.set_jobs_found(run.id, 42)
    await db_session.refresh(run)
    assert run.jobs_found == 42
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/test_runs_sp3a.py::test_set_jobs_found -v
```
Expected: `AttributeError: type object 'Run' has no attribute 'jobs_found'`

- [ ] **Step 3: Add `jobs_found` to Run model**

In `src/data/models/run.py`, add after `retry_count` line:
```python
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
```
`Integer` is already imported at the top of the file.

- [ ] **Step 4: Add `set_jobs_found` to RunsRepository**

In `src/data/repositories/runs.py`, add after imports:
```python
from sqlalchemy import select, update
```
Then add method after `get_by_id`:
```python
    async def set_jobs_found(self, run_id, count: int) -> None:
        await self.session.execute(
            update(Run).where(Run.id == run_id).values(jobs_found=count)
        )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/api/test_runs_sp3a.py::test_set_jobs_found -v
```
Expected: `PASSED` — if the DB still has the old schema, the test will fail with a column error. That's expected until the migration runs. Skip to Step 6 first.

- [ ] **Step 6: Generate Alembic migration**

```bash
cd /home/pk/Work/projects/job-automation-ai
alembic -c src/data/migrations/alembic.ini revision --autogenerate -m "add_jobs_found_to_runs"
```

Check the generated file in `src/data/migrations/versions/` — verify it adds:
```python
op.add_column('runs', sa.Column('jobs_found', sa.Integer(), nullable=False, server_default='0'))
```
If autogenerate missed it, write manually:

```python
"""add jobs_found to runs

Revision ID: <auto-generated>
Revises: 2d1d8aa4e94c
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = '<auto-generated>'
down_revision = '2d1d8aa4e94c'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('runs', sa.Column('jobs_found', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:
    op.drop_column('runs', 'jobs_found')
```

- [ ] **Step 7: Run test again to verify it passes with new schema**

```bash
pytest tests/api/test_runs_sp3a.py::test_set_jobs_found -v
```
Expected: `PASSED`

- [ ] **Step 8: Commit**

```bash
git add src/data/models/run.py src/data/repositories/runs.py \
        src/data/migrations/versions/ tests/api/test_runs_sp3a.py
git commit -m "feat(backend): add jobs_found to Run model + set_jobs_found()

- By Pravin Kamdi"
```

---

## Task 2: Extend `RunOut` schema with `jobs_found`, `steps`, `error_details`

**Files:**
- Modify: `src/api/schemas/runs.py`
- Modify: `tests/api/test_runs_sp3a.py`

- [ ] **Step 1: Write failing test**

Add to `tests/api/test_runs_sp3a.py`:
```python
import json
import secrets

async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    s = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{s}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": s})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={"bootstrap_secret": s, "public_key": pub, "signature": sig})
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_run_out_has_jobs_found(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get("/api/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # If any runs exist, they should have jobs_found field
    data = r.json()
    assert "items" in data
    if data["items"]:
        assert "jobs_found" in data["items"][0]
        assert "steps" in data["items"][0]
        assert "error_details" in data["items"][0]
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/api/test_runs_sp3a.py::test_run_out_has_jobs_found -v
```
Expected: `FAILED` — `jobs_found` not in response item (if items exist) or passes vacuously (no items). Either way, add the fields.

- [ ] **Step 3: Extend `RunOut`**

Replace `src/api/schemas/runs.py` with:
```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RunOut(BaseModel):
    id: uuid.UUID
    kind: str
    correlation_id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_details: dict | None = None
    steps: list = []
    jobs_found: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/api/test_runs_sp3a.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/runs.py tests/api/test_runs_sp3a.py
git commit -m "feat(backend): expose jobs_found, steps, error_details in RunOut

- By Pravin Kamdi"
```

---

## Task 3: Wire `set_jobs_found()` into the scrape task

**Files:**
- Modify: `src/tasks/scrape.py`
- Modify: `tests/api/test_runs_sp3a.py`

- [ ] **Step 1: Write failing test**

Add to `tests/api/test_runs_sp3a.py`:
```python
@pytest.mark.asyncio(loop_scope="session")
async def test_scrape_sets_jobs_found(db_session):
    """After _persist runs, jobs_found on the matching run row equals len(jobs)."""
    from unittest.mock import MagicMock, patch
    from src.tasks.scrape import _scrape_and_persist
    from src.data.models.run import Run
    import uuid

    correlation_id = str(uuid.uuid4())

    # Pre-create the run row that pipeline_task would normally create
    run = Run(kind="scrape", correlation_id=correlation_id, status="running")
    db_session.add(run)
    await db_session.commit()

    fake_job = MagicMock()
    fake_job.source = "linkedin"
    fake_job.job_id = "test-123"
    fake_job.title = "Engineer"
    fake_job.company = "Acme"
    fake_job.description = "desc"
    fake_job.url = "https://example.com"

    with patch("src.tasks.scrape.ScraperService") as MockSvc, \
         patch("src.tasks.scrape.load_config"), \
         patch("src.tasks.scrape.Path"):
        MockSvc.return_value.scrape.return_value = [fake_job]
        result = _scrape_and_persist(correlation_id)

    assert result["jobs_scraped"] == 1
    await db_session.refresh(run)
    assert run.jobs_found == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/api/test_runs_sp3a.py::test_scrape_sets_jobs_found -v
```
Expected: `FAILED — assert run.jobs_found == 1` (it will be 0)

- [ ] **Step 3: Update `_scrape_and_persist` to call `set_jobs_found`**

Replace the `_persist` inner function in `src/tasks/scrape.py`:

```python
def _scrape_and_persist(correlation_id: str) -> dict:
    import asyncio
    from pathlib import Path

    from src.data.db import get_sessionmaker
    from src.data.repositories.jobs import JobsRepository
    from src.data.repositories.runs import RunsRepository
    from src.observability.logging import get_logger
    from src.scraper.service import ScraperService
    from src.utils.config import load_config

    log = get_logger("tasks.scrape")
    config = load_config(Path("config.yaml"))
    service = ScraperService(config, Path("."), log)
    jobs = service.scrape()

    async def _persist() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            jobs_repo = JobsRepository(session)
            for j in jobs:
                await jobs_repo.upsert(
                    source=j.source,
                    source_id=j.job_id,
                    title=j.title,
                    company=j.company,
                    jd_text=j.description or "",
                    url=j.url,
                )
            count = len(jobs)
            runs_repo = RunsRepository(session)
            run, _ = await runs_repo.get_or_create(kind="scrape", correlation_id=correlation_id)
            await runs_repo.set_jobs_found(run.id, count)
            await session.commit()
        return count

    count = asyncio.run(_persist())
    return {"jobs_scraped": count}
```

- [ ] **Step 4: Run to verify it passes**

```bash
pytest tests/api/test_runs_sp3a.py::test_scrape_sets_jobs_found -v
```
Expected: `PASSED`

- [ ] **Step 5: Run all backend tests to check for regressions**

```bash
pytest tests/api/ tests/tasks/ -v
```
Expected: all existing tests pass + new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/tasks/scrape.py tests/api/test_runs_sp3a.py
git commit -m "feat(backend): scrape task sets jobs_found on Run after persist

- By Pravin Kamdi"
```

---

## Task 4: Fix `_push_on_complete` to load FCM tokens from DB

**Problem:** `PushService.send_fcm_all` iterates `self._fcm_tokens` (in-memory list, always empty at runtime). Registered tokens live in the `fcm_tokens` DB table via `FcmTokensRepository`.

**Files:**
- Modify: `src/notifications/push.py`
- Modify: `src/tasks/base.py`
- Create: `tests/notifications/test_push_sp3a.py`

- [ ] **Step 1: Write failing test**

```python
# tests/notifications/test_push_sp3a.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.notifications.push import PushEvent, PushService


def test_send_fcm_all_uses_provided_tokens():
    """send_fcm_all must use the tokens argument, not self._fcm_tokens."""
    svc = PushService(fcm_project_id="proj", fcm_service_account_json="{}")
    # Do NOT call svc.register_fcm_token — that simulates the real-world state
    with patch.object(svc, "_send_fcm_single") as mock_send:
        svc.send_fcm_all(PushEvent(title="T", body="B"), tokens=["tok1", "tok2"])
    assert mock_send.call_count == 2


def test_send_event_passes_tokens_through():
    """send_event must forward the tokens kwarg to send_fcm_all."""
    svc = PushService(fcm_project_id="proj", fcm_service_account_json="{}")
    with patch.object(svc, "send_ntfy"), patch.object(svc, "send_fcm_all") as mock_fcm:
        svc.send_event(PushEvent(title="T", body="B"), tokens=["tokA"])
    mock_fcm.assert_called_once_with(PushEvent(title="T", body="B"), tokens=["tokA"])
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest tests/notifications/test_push_sp3a.py -v
```
Expected: `FAILED` — `send_fcm_all` / `send_event` don't accept `tokens` kwarg yet.

- [ ] **Step 3: Update `PushService` in `src/notifications/push.py`**

Change `send_event` and `send_fcm_all` signatures to accept `tokens`:

```python
    def send_event(self, event: PushEvent, tokens: list[str] | None = None) -> None:
        self.send_ntfy(event)
        self.send_fcm_all(event, tokens=tokens or [])

    def send_fcm_all(self, event: PushEvent, tokens: list[str] | None = None) -> None:
        effective_tokens = tokens if tokens is not None else self._fcm_tokens
        for token in effective_tokens:
            self._send_fcm_single(event, token)
```

If `_send_fcm_single` doesn't exist yet (FCM was called inline), refactor the per-token FCM send into `_send_fcm_single(self, event, token)`. Check the current `send_fcm_all` body and extract the per-token loop into that private method.

- [ ] **Step 4: Update `_push_on_complete` in `src/tasks/base.py`**

Replace the existing `_push_on_complete` function:

```python
def _push_on_complete(stage: str, result: dict) -> None:
    """Fire push after pipeline stage completes. Loads FCM tokens from DB. Never raises."""
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
            data=result,
        ), tokens=tokens)
    except Exception:
        log.debug("Push notification skipped (not configured or error)", exc_info=True)
```

- [ ] **Step 5: Run new tests**

```bash
pytest tests/notifications/test_push_sp3a.py -v
```
Expected: `PASSED`

- [ ] **Step 6: Run full notification test suite**

```bash
pytest tests/notifications/ -v
```
Expected: all pass (old + new).

- [ ] **Step 7: Commit**

```bash
git add src/notifications/push.py src/tasks/base.py tests/notifications/test_push_sp3a.py
git commit -m "fix(backend): load FCM tokens from DB in _push_on_complete instead of in-memory list

- By Pravin Kamdi"
```

---

## Task 5: Update `JobAiService.kt` — new DTOs and endpoints

Fix the `listRuns` return type bug (returns `List<RunDto>` but backend returns paginated), add `jobsFound` to `RunDto`, add DLQ DTOs/endpoints, Gmail status, FCM register, device delete.

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/core/api/JobAiService.kt`

- [ ] **Step 1: Update `RunDto` and add new DTOs**

Replace the `RunDto` and add new types in `JobAiService.kt`:

```kotlin
@JsonClass(generateAdapter = true)
data class RunDto(
    val id: String,
    val kind: String,
    val status: String,
    @Json(name = "started_at") val startedAt: String,
    @Json(name = "finished_at") val finishedAt: String?,
    @Json(name = "jobs_found") val jobsFound: Int = 0,
    @Json(name = "error_code") val errorCode: String? = null,
)

@JsonClass(generateAdapter = true)
data class PaginatedRuns(
    val items: List<RunDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

@JsonClass(generateAdapter = true)
data class DlqDto(
    val id: String,
    val kind: String,
    @Json(name = "correlation_id") val correlationId: String,
    val status: String,
    @Json(name = "error_code") val errorCode: String?,
    @Json(name = "retry_count") val retryCount: Int,
    @Json(name = "started_at") val startedAt: String?,
    @Json(name = "finished_at") val finishedAt: String?,
)

@JsonClass(generateAdapter = true)
data class PaginatedDlq(
    val items: List<DlqDto>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "has_next") val hasNext: Boolean,
)

@JsonClass(generateAdapter = true)
data class GmailStatusDto(val authorized: Boolean)

@JsonClass(generateAdapter = true)
data class FcmRegisterRequest(val token: String, @Json(name = "device_id") val deviceId: String)

@JsonClass(generateAdapter = true)
data class FcmRegisterOut(val registered: Boolean)

@JsonClass(generateAdapter = true)
data class DlqActionOut(val queued: Boolean? = null, val dismissed: Boolean? = null)
```

- [ ] **Step 2: Update Retrofit interface methods**

Replace `listRuns` and add new methods at the bottom of the `JobAiService` interface:

```kotlin
    @GET("runs")
    suspend fun listRuns(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 20,
    ): PaginatedRuns

    @GET("runs/{id}")
    suspend fun getRunDetail(@Path("id") id: String): RunDto

    @GET("dlq")
    suspend fun listDlq(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 50,
    ): PaginatedDlq

    @POST("dlq/{id}/retry")
    suspend fun retryDlqItem(@Path("id") id: String): DlqActionOut

    @POST("dlq/{id}/dismiss")
    suspend fun dismissDlqItem(@Path("id") id: String): DlqActionOut

    @GET("gmail/status")
    suspend fun gmailStatus(): GmailStatusDto

    @POST("notifications/fcm/register")
    suspend fun registerFcmToken(@Body body: FcmRegisterRequest): FcmRegisterOut

    @DELETE("devices/{deviceId}")
    suspend fun deleteDevice(@Path("deviceId") deviceId: String): Unit
```

- [ ] **Step 3: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL` (or only errors in files not yet updated — `RunsRepository` still calls old `listRuns` signature, that's fine for now).

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/core/api/JobAiService.kt
git commit -m "feat(android): update JobAiService — RunDto jobsFound, paginated runs, DLQ/Gmail/FCM endpoints

- By Pravin Kamdi"
```

---

## Task 6: Firebase setup

**Files:**
- Modify: `android/libs.versions.toml`
- Modify: `android/app/build.gradle.kts`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/google-services.json`

- [ ] **Step 1: Add Firebase versions to `libs.versions.toml`**

In the `[versions]` section, add:
```toml
firebase-bom = "33.1.0"
```

In the `[libraries]` section, add:
```toml
firebase-messaging-ktx = { group = "com.google.firebase", name = "firebase-messaging-ktx" }
```

In the `[plugins]` section, add:
```toml
google-services = { id = "com.google.gms.google-services", version = "4.4.2" }
```

- [ ] **Step 2: Update `android/app/build.gradle.kts`**

At the top plugins block, add:
```kotlin
alias(libs.plugins.google.services)
```

In the `dependencies` block, add:
```kotlin
implementation(platform("com.google.firebase:firebase-bom:33.1.0"))
implementation(libs.firebase.messaging.ktx)
```

- [ ] **Step 3: Update `android/build.gradle.kts` (project-level)**

Add to `plugins` block at the top:
```kotlin
alias(libs.plugins.google.services) apply false
```

- [ ] **Step 4: Create stub `google-services.json`**

Create `android/app/google-services.json` with this placeholder (build succeeds; FCM won't work at runtime until replaced with real file from Firebase Console):

```json
{
  "project_info": {
    "project_number": "000000000000",
    "project_id": "jobai-companion-stub",
    "storage_bucket": "jobai-companion-stub.appspot.com"
  },
  "client": [
    {
      "client_info": {
        "mobilesdk_app_id": "1:000000000000:android:0000000000000000000000",
        "android_client_info": {
          "package_name": "com.jobai.companion"
        }
      },
      "oauth_client": [],
      "api_key": [
        {
          "current_key": "REPLACE_WITH_REAL_API_KEY"
        }
      ],
      "services": {
        "appinvite_service": {
          "other_platform_oauth_client": []
        }
      }
    }
  ],
  "configuration_version": "1"
}
```

- [ ] **Step 5: Add FCM service to `AndroidManifest.xml`**

Inside the `<application>` tag, add:
```xml
<service
    android:name=".firebase.JobAiFirebaseService"
    android:exported="false">
    <intent-filter>
        <action android:name="com.google.firebase.MESSAGING_EVENT" />
    </intent-filter>
</service>
```

Before the `<application>` tag, add:
```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```

- [ ] **Step 6: Verify build**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL` (the service class doesn't exist yet — that's fine, manifest references are not checked at compile time).

- [ ] **Step 7: Commit**

```bash
git add android/libs.versions.toml android/app/build.gradle.kts \
        android/build.gradle.kts android/app/google-services.json \
        android/app/src/main/AndroidManifest.xml
git commit -m "feat(android): Firebase Messaging setup — stub google-services.json, manifest

- By Pravin Kamdi"
```

---

## Task 7: `JobAiFirebaseService` + `FcmModule` + FCM registration in `AuthRepository`

**Files:**
- Create: `android/app/src/main/java/com/jobai/companion/firebase/JobAiFirebaseService.kt`
- Create: `android/app/src/main/java/com/jobai/companion/firebase/FcmModule.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/auth/AuthRepository.kt`

- [ ] **Step 1: Create `FcmModule.kt`**

```kotlin
// firebase/FcmModule.kt
package com.jobai.companion.firebase

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import javax.inject.Qualifier
import javax.inject.Singleton

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ApplicationScope

@Module
@InstallIn(SingletonComponent::class)
object FcmModule {
    @Provides
    @Singleton
    @ApplicationScope
    fun provideApplicationScope(): CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.IO)
}
```

- [ ] **Step 2: Create `JobAiFirebaseService.kt`**

```kotlin
// firebase/JobAiFirebaseService.kt
package com.jobai.companion.firebase

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.jobai.companion.core.api.FcmRegisterRequest
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.auth.SessionStore
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import javax.inject.Inject

private const val CHANNEL_ID = "jobai_pipeline"
private const val CHANNEL_NAME = "Pipeline Events"

@AndroidEntryPoint
class JobAiFirebaseService : FirebaseMessagingService() {

    @Inject lateinit var api: JobAiService
    @Inject lateinit var sessionStore: SessionStore
    @Inject @ApplicationScope lateinit var scope: CoroutineScope

    override fun onNewToken(token: String) {
        val deviceId = sessionStore.deviceId ?: return
        scope.launch {
            runCatching { api.registerFcmToken(FcmRegisterRequest(token = token, deviceId = deviceId)) }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val title = message.notification?.title ?: message.data["title"] ?: "JobAI"
        val body = message.notification?.body ?: message.data["body"] ?: ""
        showNotification(title, body)
    }

    private fun showNotification(title: String, body: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_DEFAULT)
        manager.createNotificationChannel(channel)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        manager.notify(System.currentTimeMillis().toInt(), notification)
    }
}
```

- [ ] **Step 3: Register FCM token in `AuthRepository` after successful pair**

In `auth/AuthRepository.kt`, add after the `sessionStore.serverUrl = serverUrl` line inside `pair()`:

```kotlin
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.tasks.await
```

And inside the `pair()` runCatching block, after storing session:
```kotlin
runCatching {
    val fcmToken = FirebaseMessaging.getInstance().token.await()
    api.registerFcmToken(
        com.jobai.companion.core.api.FcmRegisterRequest(token = fcmToken, deviceId = pairResp.deviceId)
    )
}
```

The full updated `pair()` in `AuthRepository.kt`:
```kotlin
suspend fun pair(bootstrapSecret: String, serverUrl: String): PairResult = runCatching {
    keystoreHelper.ensureKeyPairExists()
    val challengeHex = api.challenge(ChallengeRequest(bootstrapSecret)).challenge
    val pairResp = api.pair(
        PairRequest(bootstrapSecret, keystoreHelper.publicKeyHexDer, keystoreHelper.signHex(challengeHex))
    )
    sessionStore.sessionToken = pairResp.sessionToken
    sessionStore.deviceId = pairResp.deviceId
    sessionStore.serverUrl = serverUrl
    runCatching {
        val fcmToken = com.google.firebase.messaging.FirebaseMessaging.getInstance().token.await()
        api.registerFcmToken(
            com.jobai.companion.core.api.FcmRegisterRequest(token = fcmToken, deviceId = pairResp.deviceId)
        )
    }
    PairResult.Success(pairResp.deviceId)
}.getOrElse { PairResult.Error(it.message ?: "Pairing failed") }
```

- [ ] **Step 4: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/firebase/ \
        android/app/src/main/java/com/jobai/companion/auth/AuthRepository.kt
git commit -m "feat(android): FCM service + token registration after pair

- By Pravin Kamdi"
```

---

## Task 8: DLQ data layer — Room entity, DAO, AppDatabase migration, Repository, ViewModel, Screen

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/core/db/AppDatabase.kt`
- Create: `android/app/src/main/java/com/jobai/companion/dlq/DlqRepository.kt`
- Create: `android/app/src/main/java/com/jobai/companion/dlq/DlqViewModel.kt`
- Create: `android/app/src/main/java/com/jobai/companion/dlq/DlqScreen.kt`

- [ ] **Step 1: Add `DlqEntity` and `DlqDao` to `AppDatabase.kt`**

Add these classes before the `@Database` annotation:

```kotlin
@Entity(tableName = "dlq_items")
data class DlqEntity(
    @PrimaryKey val id: String,
    val kind: String,
    val correlationId: String,
    val status: String,
    val errorCode: String?,
    val retryCount: Int,
    val startedAt: Long?,
    val finishedAt: Long?,
    val syncedAt: Long,
)

@Dao
interface DlqDao {
    @Query("SELECT * FROM dlq_items ORDER BY startedAt DESC")
    fun observeAll(): Flow<List<DlqEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<DlqEntity>)

    @Query("DELETE FROM dlq_items WHERE id = :id")
    suspend fun delete(id: String)
}
```

Update `@Database` annotation to include `DlqEntity` and bump version to 3:
```kotlin
@Database(
    entities = [JobEntity::class, ApplicationEntity::class, RunEntity::class, DlqEntity::class],
    version = 3,
    exportSchema = false,
)
```

Add `abstract fun dlqDao(): DlqDao` to the database class.

Add a `Migration(2, 3)` inside the database builder call in `DatabaseModule.kt`:

```kotlin
// In core/di/DatabaseModule.kt, update the Room.databaseBuilder call:
Room.databaseBuilder(context, AppDatabase::class.java, "jobai.db")
    .addMigrations(
        object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("""
                    CREATE TABLE IF NOT EXISTS dlq_items (
                        id TEXT NOT NULL PRIMARY KEY,
                        kind TEXT NOT NULL,
                        correlationId TEXT NOT NULL,
                        status TEXT NOT NULL,
                        errorCode TEXT,
                        retryCount INTEGER NOT NULL,
                        startedAt INTEGER,
                        finishedAt INTEGER,
                        syncedAt INTEGER NOT NULL
                    )
                """.trimIndent())
            }
        }
    )
    .build()
```

Also add `DlqDao` provider to `DatabaseModule.kt`:
```kotlin
@Provides fun provideDlqDao(db: AppDatabase): DlqDao = db.dlqDao()
```

- [ ] **Step 2: Create `DlqRepository.kt`**

```kotlin
// dlq/DlqRepository.kt
package com.jobai.companion.dlq

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.DlqDao
import com.jobai.companion.core.db.DlqEntity
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

data class DlqItem(
    val id: String,
    val kind: String,
    val status: String,
    val errorCode: String?,
    val retryCount: Int,
    val startedAt: Instant?,
)

@Singleton
class DlqRepository @Inject constructor(
    private val dlqDao: DlqDao,
    private val api: JobAiService,
) {
    val dlqFlow: Flow<List<DlqItem>> = dlqDao.observeAll().map { entities ->
        entities.map {
            DlqItem(
                id = it.id,
                kind = it.kind,
                status = it.status,
                errorCode = it.errorCode,
                retryCount = it.retryCount,
                startedAt = it.startedAt?.let(Instant::ofEpochMilli),
            )
        }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        val resp = api.listDlq()
        dlqDao.upsertAll(resp.items.map { dto ->
            DlqEntity(
                id = dto.id,
                kind = dto.kind,
                correlationId = dto.correlationId,
                status = dto.status,
                errorCode = dto.errorCode,
                retryCount = dto.retryCount,
                startedAt = dto.startedAt?.let { Instant.parse(it).toEpochMilli() },
                finishedAt = dto.finishedAt?.let { Instant.parse(it).toEpochMilli() },
                syncedAt = now,
            )
        })
    }

    suspend fun retry(itemId: String) {
        runCatching { api.retryDlqItem(itemId) }
        sync()
    }

    suspend fun dismiss(itemId: String) {
        runCatching { api.dismissDlqItem(itemId) }
        dlqDao.delete(itemId)
    }
}
```

- [ ] **Step 3: Create `DlqViewModel.kt`**

```kotlin
// dlq/DlqViewModel.kt
package com.jobai.companion.dlq

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DlqUiState(
    val items: List<DlqItem> = emptyList(),
    val isRefreshing: Boolean = false,
)

@HiltViewModel
class DlqViewModel @Inject constructor(
    private val repo: DlqRepository,
) : ViewModel() {

    private val _isRefreshing = MutableStateFlow(false)

    val uiState: StateFlow<DlqUiState> = combine(repo.dlqFlow, _isRefreshing) { items, refreshing ->
        DlqUiState(items = items, isRefreshing = refreshing)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DlqUiState())

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun retry(itemId: String) {
        viewModelScope.launch {
            runCatching { repo.retry(itemId) }
        }
    }

    fun dismiss(itemId: String) {
        viewModelScope.launch {
            runCatching { repo.dismiss(itemId) }
        }
    }
}
```

- [ ] **Step 4: Create `DlqScreen.kt`**

```kotlin
// dlq/DlqScreen.kt
package com.jobai.companion.dlq

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.theme.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val dlqDateFmt = DateTimeFormatter.ofPattern("MMM d, HH:mm").withZone(ZoneId.systemDefault())

@Composable
fun DlqScreen(onBack: () -> Unit, vm: DlqViewModel = hiltViewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().background(Background)) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("← Back", color = Primary) }
            Spacer(Modifier.width(8.dp))
            Text("Failed Runs", style = AppTypography.headlineMedium, color = TextPrimary)
        }

        if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)

        if (state.items.isEmpty() && !state.isRefreshing) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No failed runs", style = AppTypography.titleMedium, color = TextMuted)
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.items, key = { it.id }) { item ->
                    DlqCard(item, onRetry = { vm.retry(item.id) }, onDismiss = { vm.dismiss(item.id) })
                }
            }
        }
    }
}

@Composable
private fun DlqCard(item: DlqItem, onRetry: () -> Unit, onDismiss: () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(item.kind.replaceFirstChar { it.uppercase() }, style = AppTypography.titleMedium, color = TextPrimary)
                    item.errorCode?.let {
                        Text(it, style = AppTypography.bodySmall, color = ScoreLow)
                    }
                    item.startedAt?.let {
                        Text(dlqDateFmt.format(it), style = AppTypography.labelSmall, color = TextDisabled)
                    }
                }
                Text("× ${item.retryCount}", style = AppTypography.labelSmall, color = TextMuted)
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                ) { Text("Retry", color = Primary) }
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                ) { Text("Dismiss", color = TextMuted) }
            }
        }
    }
}
```

- [ ] **Step 5: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/core/db/AppDatabase.kt \
        android/app/src/main/java/com/jobai/companion/core/di/DatabaseModule.kt \
        android/app/src/main/java/com/jobai/companion/dlq/
git commit -m "feat(android): DLQ data layer — Room entity, Repository, ViewModel, Screen

- By Pravin Kamdi"
```

---

## Task 9: Add `Screen.Dlq` to `AppNavigation`

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt`

- [ ] **Step 1: Add `Screen.Dlq` and wire `DlqScreen`**

In `AppNavigation.kt`:

1. Add to the `Screen` sealed class:
```kotlin
object Dlq : Screen("dlq")
```

2. After `composable(Screen.Runs.route) { RunsScreen() }`, add:
```kotlin
composable(Screen.Dlq.route) {
    DlqScreen(onBack = { navController.popBackStack() })
}
```

3. Add import:
```kotlin
import com.jobai.companion.dlq.DlqScreen
```

- [ ] **Step 2: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt
git commit -m "feat(android): add Screen.Dlq route to AppNavigation

- By Pravin Kamdi"
```

---

## Task 10: Settings feature — Repository, GmailOAuthPoller, ViewModel, Screen

**Files:**
- Create: `android/app/src/main/java/com/jobai/companion/settings/SettingsRepository.kt`
- Create: `android/app/src/main/java/com/jobai/companion/settings/GmailOAuthPoller.kt`
- Create: `android/app/src/main/java/com/jobai/companion/settings/SettingsViewModel.kt`
- Create: `android/app/src/main/java/com/jobai/companion/settings/SettingsScreen.kt`

- [ ] **Step 1: Create `SettingsRepository.kt`**

```kotlin
// settings/SettingsRepository.kt
package com.jobai.companion.settings

import com.jobai.companion.auth.AuthRepository
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.auth.SessionStore
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SettingsRepository @Inject constructor(
    private val api: JobAiService,
    private val sessionStore: SessionStore,
    private val authRepository: AuthRepository,
) {
    val serverUrl: String get() = sessionStore.serverUrl ?: "—"
    val deviceId: String get() = sessionStore.deviceId ?: "—"

    suspend fun gmailAuthorized(): Boolean =
        runCatching { api.gmailStatus().authorized }.getOrDefault(false)

    suspend fun unpair() {
        val deviceId = sessionStore.deviceId
        runCatching {
            com.google.firebase.messaging.FirebaseMessaging.getInstance().token.await()
                .let { token -> api.registerFcmToken(
                    com.jobai.companion.core.api.FcmRegisterRequest(token = token, deviceId = deviceId ?: "")
                ) }
        }
        if (deviceId != null) runCatching { api.deleteDevice(deviceId) }
        authRepository.unpair()
    }
}
```

Add this import at the top:
```kotlin
import kotlinx.coroutines.tasks.await
```

- [ ] **Step 2: Create `GmailOAuthPoller.kt`**

```kotlin
// settings/GmailOAuthPoller.kt
package com.jobai.companion.settings

import com.jobai.companion.core.api.JobAiService
import kotlinx.coroutines.delay
import javax.inject.Inject

sealed class PollResult { object Authorized : PollResult(); object TimedOut : PollResult() }

class GmailOAuthPoller @Inject constructor(private val api: JobAiService) {
    suspend fun pollUntilAuthorized(timeoutMs: Long = 300_000L, intervalMs: Long = 3_000L): PollResult {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            val status = runCatching { api.gmailStatus() }.getOrNull()
            if (status?.authorized == true) return PollResult.Authorized
            delay(intervalMs)
        }
        return PollResult.TimedOut
    }
}
```

- [ ] **Step 3: Create `SettingsViewModel.kt`**

```kotlin
// settings/SettingsViewModel.kt
package com.jobai.companion.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val serverUrl: String = "",
    val deviceId: String = "",
    val gmailAuthorized: Boolean = false,
    val isUnpairing: Boolean = false,
    val isPollingGmail: Boolean = false,
    val gmailPollTimedOut: Boolean = false,
    val navigateToWelcome: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repo: SettingsRepository,
    private val gmailPoller: GmailOAuthPoller,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        _state.update { it.copy(serverUrl = repo.serverUrl, deviceId = repo.deviceId) }
        viewModelScope.launch {
            val authorized = repo.gmailAuthorized()
            _state.update { it.copy(gmailAuthorized = authorized) }
        }
    }

    fun startGmailOAuthPoll() {
        viewModelScope.launch {
            _state.update { it.copy(isPollingGmail = true, gmailPollTimedOut = false) }
            val result = gmailPoller.pollUntilAuthorized()
            when (result) {
                is PollResult.Authorized -> _state.update { it.copy(gmailAuthorized = true, isPollingGmail = false) }
                is PollResult.TimedOut -> _state.update { it.copy(gmailPollTimedOut = true, isPollingGmail = false) }
            }
        }
    }

    fun unpair() {
        viewModelScope.launch {
            _state.update { it.copy(isUnpairing = true) }
            runCatching { repo.unpair() }
            _state.update { it.copy(isUnpairing = false, navigateToWelcome = true) }
        }
    }

    fun onNavigatedToWelcome() {
        _state.update { it.copy(navigateToWelcome = false) }
    }
}
```

- [ ] **Step 4: Create `SettingsScreen.kt`**

```kotlin
// settings/SettingsScreen.kt
package com.jobai.companion.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.theme.*

@Composable
fun SettingsScreen(
    onUnpaired: () -> Unit,
    vm: SettingsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val uriHandler = LocalUriHandler.current
    var showUnpairDialog by remember { mutableStateOf(false) }

    LaunchedEffect(state.navigateToWelcome) {
        if (state.navigateToWelcome) {
            vm.onNavigatedToWelcome()
            onUnpaired()
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Background)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Settings", style = AppTypography.headlineMedium, color = TextPrimary)

        // Device section
        SectionCard(title = "Device") {
            LabelValue("Server", state.serverUrl)
            LabelValue("Device ID", state.deviceId.take(16), monospace = true)
        }

        // Gmail section
        SectionCard(title = "Gmail") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (state.gmailAuthorized) "Connected" else "Not connected",
                    style = AppTypography.bodyMedium,
                    color = if (state.gmailAuthorized) ScoreHigh else TextMuted,
                    modifier = Modifier.weight(1f),
                )
                if (!state.gmailAuthorized) {
                    Button(
                        onClick = {
                            uriHandler.openUri("https://accounts.google.com/o/oauth2/device/code")
                            vm.startGmailOAuthPoll()
                        },
                        enabled = !state.isPollingGmail,
                        colors = ButtonDefaults.buttonColors(containerColor = Primary),
                        shape = RoundedCornerShape(8.dp),
                    ) { Text(if (state.isPollingGmail) "Waiting…" else "Connect", color = Color.White) }
                }
            }
            if (state.gmailPollTimedOut) {
                Text("OAuth timed out — try again", style = AppTypography.labelSmall, color = ScoreLow)
            }
        }

        Spacer(Modifier.weight(1f))

        // Unpair
        Button(
            onClick = { showUnpairDialog = true },
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = ScoreLow),
            enabled = !state.isUnpairing,
        ) {
            Text(if (state.isUnpairing) "Unpairing…" else "Unpair Device", color = Color.White)
        }
    }

    if (showUnpairDialog) {
        AlertDialog(
            onDismissRequest = { showUnpairDialog = false },
            title = { Text("Unpair device?") },
            text = { Text("This clears your session and keys. You will need to scan a QR code to reconnect.") },
            confirmButton = {
                TextButton(onClick = { showUnpairDialog = false; vm.unpair() }) {
                    Text("Unpair", color = ScoreLow)
                }
            },
            dismissButton = {
                TextButton(onClick = { showUnpairDialog = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = AppTypography.labelMedium, color = TextMuted)
            content()
        }
    }
}

@Composable
private fun LabelValue(label: String, value: String, monospace: Boolean = false) {
    Row {
        Text("$label: ", style = AppTypography.bodyMedium, color = TextMuted)
        Text(
            value,
            style = if (monospace) AppTypography.bodyMedium.copy(fontFamily = FiraCodeFamily)
                    else AppTypography.bodyMedium,
            color = TextPrimary,
        )
    }
}
```

- [ ] **Step 5: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/settings/
git commit -m "feat(android): Settings screen — device info, Gmail OAuth, unpair

- By Pravin Kamdi"
```

---

## Task 11: Wire Settings into `AppNavigation` — replace stub, add unpair nav

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt`

- [ ] **Step 1: Replace Settings stub and wire unpair navigation**

In `AppNavigation.kt`:

1. Add import:
```kotlin
import com.jobai.companion.settings.SettingsScreen
```

2. Replace:
```kotlin
composable(Screen.More.route) {
    Text("Settings coming in SP3")
}
```
With:
```kotlin
composable(Screen.More.route) {
    SettingsScreen(
        onUnpaired = {
            navController.navigate(Screen.Welcome.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    )
}
```

- [ ] **Step 2: Verify compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt
git commit -m "feat(android): wire SettingsScreen into AppNavigation, replace stub

- By Pravin Kamdi"
```

---

## Task 12: RunsScreen enrichment — `jobsFound` chip, error accordion, DLQ badge, fix paginated response

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/runs/RunsRepository.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/runs/RunsViewModel.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/runs/RunsScreen.kt`

- [ ] **Step 1: Fix `RunsRepository` — paginated response + `jobsFound`**

Replace `RunsRepository.kt` content:

```kotlin
package com.jobai.companion.runs

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.RunDao
import com.jobai.companion.core.db.RunEntity
import com.jobai.companion.core.model.Run
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RunsRepository @Inject constructor(
    private val runDao: RunDao,
    private val api: JobAiService,
) {
    val runsFlow: Flow<List<Run>> = runDao.observeRecent().map { entities ->
        entities.map {
            Run(
                id = it.id,
                kind = it.kind,
                status = it.status,
                startedAt = Instant.ofEpochMilli(it.startedAt),
                finishedAt = it.finishedAt?.let(Instant::ofEpochMilli),
                jobsFound = it.jobsFound,
            )
        }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        val resp = api.listRuns(perPage = 20)
        runDao.upsertAll(resp.items.map { dto ->
            RunEntity(
                id = dto.id,
                kind = dto.kind,
                status = dto.status,
                startedAt = Instant.parse(dto.startedAt).toEpochMilli(),
                finishedAt = dto.finishedAt?.let { Instant.parse(it).toEpochMilli() },
                jobsFound = dto.jobsFound,
                syncedAt = now,
            )
        })
    }

    suspend fun triggerRun() = api.triggerRun()

    suspend fun getRunDetail(id: String) = runCatching { api.getRunDetail(id) }.getOrNull()
}
```

- [ ] **Step 2: Update `RunsViewModel` — add `selectedRunId` and `loadDetail`**

Replace `RunsViewModel.kt`:

```kotlin
package com.jobai.companion.runs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.RunDto
import com.jobai.companion.core.model.Run
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RunsUiState(
    val runs: List<Run> = emptyList(),
    val isRefreshing: Boolean = false,
    val triggerPending: Boolean = false,
    val selectedRunId: String? = null,
    val selectedDetail: RunDto? = null,
)

@HiltViewModel
class RunsViewModel @Inject constructor(
    private val repo: RunsRepository,
) : ViewModel() {

    private val _isRefreshing = MutableStateFlow(false)
    private val _triggerPending = MutableStateFlow(false)
    private val _selectedRunId = MutableStateFlow<String?>(null)
    private val _selectedDetail = MutableStateFlow<RunDto?>(null)

    val uiState: StateFlow<RunsUiState> = combine(
        repo.runsFlow, _isRefreshing, _triggerPending, _selectedRunId, _selectedDetail
    ) { runs, refreshing, trigger, selectedId, detail ->
        RunsUiState(
            runs = runs,
            isRefreshing = refreshing,
            triggerPending = trigger,
            selectedRunId = selectedId,
            selectedDetail = detail,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), RunsUiState())

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            runCatching { repo.sync() }
            _isRefreshing.value = false
        }
    }

    fun triggerRun() {
        viewModelScope.launch {
            _triggerPending.value = true
            runCatching { repo.triggerRun() }
            _triggerPending.value = false
            refresh()
        }
    }

    fun toggleDetail(runId: String) {
        if (_selectedRunId.value == runId) {
            _selectedRunId.value = null
            _selectedDetail.value = null
        } else {
            _selectedRunId.value = runId
            viewModelScope.launch {
                _selectedDetail.value = repo.getRunDetail(runId)
            }
        }
    }
}
```

- [ ] **Step 3: Update `RunsScreen` — jobs chip, accordion, DLQ badge on FAB**

Replace `RunsScreen.kt`:

```kotlin
package com.jobai.companion.runs

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.model.Run
import com.jobai.companion.core.ui.components.StatusBadge
import com.jobai.companion.core.ui.theme.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val runDateFmt = DateTimeFormatter.ofPattern("MMM d, HH:mm").withZone(ZoneId.systemDefault())

@Composable
fun RunsScreen(
    onOpenDlq: () -> Unit,
    vm: RunsViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Box(Modifier.fillMaxSize().background(Background)) {
        Column(Modifier.fillMaxSize()) {
            Text(
                "Pipeline Runs",
                style = AppTypography.headlineMedium,
                color = TextPrimary,
                modifier = Modifier.padding(16.dp),
            )
            if (state.isRefreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Primary)
            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.runs, key = { it.id }) { run ->
                    RunRow(
                        run = run,
                        isExpanded = state.selectedRunId == run.id,
                        errorCode = if (state.selectedRunId == run.id) state.selectedDetail?.errorCode else null,
                        onTap = { vm.toggleDetail(run.id) },
                    )
                }
            }
        }

        Column(
            Modifier.align(Alignment.BottomEnd).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            horizontalAlignment = Alignment.End,
        ) {
            SmallFloatingActionButton(
                onClick = onOpenDlq,
                containerColor = ScoreLow,
            ) { Text("!", color = Color.White, style = AppTypography.titleMedium) }
            FloatingActionButton(
                onClick = { vm.triggerRun() },
                containerColor = Primary,
            ) {
                Text(if (state.triggerPending) "…" else "▶", color = Color.White)
            }
        }
    }
}

@Composable
private fun RunRow(run: Run, isExpanded: Boolean, errorCode: String?, onTap: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onTap),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(run.kind.replaceFirstChar { it.uppercase() }, style = AppTypography.titleMedium, color = TextPrimary)
                    Text(runDateFmt.format(run.startedAt), style = AppTypography.bodyMedium, color = TextMuted)
                }
                if (run.jobsFound > 0) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = PrimarySurface,
                        modifier = Modifier.padding(end = 8.dp),
                    ) {
                        Text(
                            "${run.jobsFound} jobs",
                            style = AppTypography.labelSmall,
                            color = Primary,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        )
                    }
                }
                StatusBadge(run.status)
            }
            if (isExpanded) {
                Spacer(Modifier.height(8.dp))
                HorizontalDivider(color = Border)
                Spacer(Modifier.height(8.dp))
                if (errorCode != null) {
                    Text("Error: $errorCode", style = AppTypography.bodySmall, color = ScoreLow)
                } else {
                    Text("No error details", style = AppTypography.bodySmall, color = TextDisabled)
                }
            }
        }
    }
}
```

- [ ] **Step 4: Update `AppNavigation.kt` to pass `onOpenDlq` to `RunsScreen`**

In `AppNavigation.kt`, update the `RunsScreen` composable call:
```kotlin
composable(Screen.Runs.route) {
    RunsScreen(onOpenDlq = { navController.navigate(Screen.Dlq.route) })
}
```

- [ ] **Step 5: Verify full compilation**

```bash
cd /home/pk/Work/projects/job-automation-ai/android && ./gradlew :app:compileDebugKotlin 2>&1 | tail -20
```
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/runs/ \
        android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt
git commit -m "feat(android): RunsScreen — jobsFound chip, error accordion, DLQ FAB button

- By Pravin Kamdi"
```

---

## Final: Push branch

```bash
git push origin prod/w3-console
```

---

## Self-Review Checklist

| Spec requirement | Task covering it |
|---|---|
| `jobs_found` on Run model + migration | Task 1 |
| Expose `jobs_found`, `steps`, `error_details` in RunOut | Task 2 |
| Scrape task writes `jobs_found` | Task 3 |
| FCM tokens loaded from DB at push time | Task 4 |
| FCM Firebase dependencies | Task 6 |
| `JobAiFirebaseService` + `onNewToken` registration | Task 7 |
| FCM token registered after pair | Task 7 |
| DLQ Room entity + DAO + DB migration | Task 8 |
| DLQ Repository + ViewModel + Screen | Task 8 |
| `Screen.Dlq` route | Task 9 |
| Settings — server URL, device ID display | Task 10 |
| Settings — Gmail OAuth connect + poll | Task 10 |
| Settings — Unpair with confirmation dialog | Task 10 |
| Settings wired into AppNavigation | Task 11 |
| Unpair navigates back to WelcomeScreen | Task 11 |
| `jobsFound` chip on RunRow | Task 12 |
| Error accordion on RunRow tap | Task 12 |
| DLQ badge/button on RunsScreen | Task 12 |
| Fix `listRuns` paginated response bug | Task 12 |
