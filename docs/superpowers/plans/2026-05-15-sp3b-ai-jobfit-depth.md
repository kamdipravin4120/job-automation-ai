# SP3b: AI Job-fit Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose cover letters, tailored resume text, and interview prep briefings on the Android companion app, with on-demand generation via the existing AI pipeline.

**Architecture:** Three new backend API endpoints (no DB migrations needed — `job_artifacts` and `applications.briefing_json` already exist). `ApplicationOut` schema is extended to surface `briefing_json`. The `run_tailor` Celery task's missing `tailor_for_job_id` method is implemented inline in `tailor.py`. Two new Android detail screens (`JobDetailScreen`, `ApplicationDetailScreen`) are reached by tapping cards on the existing `JobsScreen` and `TrackerScreen`. A singleton `FcmEventBus` lets the `JobDetailScreen` auto-refresh when a tailor task completes.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest-asyncio, Kotlin, Jetpack Compose, Hilt, Retrofit/Moshi, Coroutines SharedFlow

---

## File Map

| Action | File |
|---|---|
| Create | `src/data/repositories/job_artifacts.py` |
| Modify | `src/api/schemas/jobs.py` |
| Modify | `src/api/routers/jobs.py` |
| Modify | `src/tasks/tailor.py` |
| Modify | `src/tasks/base.py` |
| Modify | `src/api/schemas/applications.py` |
| Modify | `src/api/routers/applications.py` |
| Create | `tests/api/test_artifacts_sp3b.py` |
| Modify | `android/app/src/main/java/com/jobai/companion/core/api/JobAiService.kt` |
| Create | `android/app/src/main/java/com/jobai/companion/firebase/FcmEventBus.kt` |
| Modify | `android/app/src/main/java/com/jobai/companion/firebase/JobAiFirebaseService.kt` |
| Create | `android/app/src/main/java/com/jobai/companion/jobs/JobDetailViewModel.kt` |
| Create | `android/app/src/main/java/com/jobai/companion/jobs/JobDetailScreen.kt` |
| Create | `android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailViewModel.kt` |
| Create | `android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailScreen.kt` |
| Modify | `android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt` |
| Modify | `android/app/src/main/java/com/jobai/companion/jobs/JobsScreen.kt` |
| Modify | `android/app/src/main/java/com/jobai/companion/tracker/TrackerScreen.kt` |

---

## Task 1: JobArtifactsRepository + ArtifactsOut schema + GET artifacts endpoint

**Files:**
- Create: `src/data/repositories/job_artifacts.py`
- Modify: `src/api/schemas/jobs.py`
- Modify: `src/api/routers/jobs.py`
- Create: `tests/api/test_artifacts_sp3b.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_artifacts_sp3b.py`:

```python
import json
import secrets
import uuid
import pytest
from datetime import UTC, datetime


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
async def test_get_artifacts_empty(async_client, redis_client, db_session):
    from src.data.models.job import Job
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Eng", company="Corp",
              jd_text="desc", url=None)
    db_session.add(job)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{job.id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cover_letter"] is None
    assert data["resume_text"] is None
    assert data["generated_at"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_artifacts_returns_latest(async_client, redis_client, db_session):
    from src.data.models.job import Job, JobArtifact
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Dev", company="Co",
              jd_text="jd", url=None)
    db_session.add(job)
    await db_session.flush()
    db_session.add(JobArtifact(job_id=job.id, kind="cover_letter", text="v1 cover", file_path="", version=1))
    db_session.add(JobArtifact(job_id=job.id, kind="cover_letter", text="v2 cover", file_path="", version=2))
    db_session.add(JobArtifact(job_id=job.id, kind="resume_text", text="resume body", file_path="", version=1))
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{job.id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cover_letter"] == "v2 cover"
    assert data["resume_text"] == "resume body"
    assert data["generated_at"] is not None
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/api/test_artifacts_sp3b.py::test_get_artifacts_empty tests/api/test_artifacts_sp3b.py::test_get_artifacts_returns_latest -v
```

Expected: FAIL — `404` (endpoint not yet registered)

- [ ] **Step 3: Create `src/data/repositories/job_artifacts.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.job import JobArtifact


class JobArtifactsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(self, job_id: uuid.UUID, kind: str) -> JobArtifact | None:
        stmt = (
            select(JobArtifact)
            .where(JobArtifact.job_id == job_id, JobArtifact.kind == kind)
            .order_by(desc(JobArtifact.version))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        kind: str,
        text: str,
        file_path: str = "",
    ) -> JobArtifact:
        row = JobArtifact(job_id=job_id, kind=kind, text=text, file_path=file_path)
        self.session.add(row)
        await self.session.flush()
        return row
```

- [ ] **Step 4: Add `ArtifactsOut` to `src/api/schemas/jobs.py`**

Replace the full file:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobOut(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    company: str
    url: str | None
    status: str
    match_score: float | None
    scraped_at: datetime
    location: str | None
    starred: bool
    dismissed: bool

    model_config = {"from_attributes": True}


class ArtifactsOut(BaseModel):
    cover_letter: str | None = None
    resume_text: str | None = None
    generated_at: datetime | None = None
```

- [ ] **Step 5: Add `GET /{job_id}/artifacts` to `src/api/routers/jobs.py`**

Add these imports at the top of the file (after the existing imports):

```python
from src.api.schemas.jobs import ArtifactsOut, JobOut
from src.data.repositories.job_artifacts import JobArtifactsRepository
```

Then add this route at the end of the file:

```python
@router.get("/{job_id}/artifacts", response_model=ArtifactsOut)
async def get_job_artifacts(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = JobArtifactsRepository(db)
    cover = await repo.get_latest(job_id, "cover_letter")
    resume_art = await repo.get_latest(job_id, "resume_text")
    return ArtifactsOut(
        cover_letter=cover.text if cover else None,
        resume_text=resume_art.text if resume_art else None,
        generated_at=cover.generated_at if cover else None,
    )
```

Note: the existing `from src.api.schemas.jobs import JobOut` line at the top must be updated to also import `ArtifactsOut`.

- [ ] **Step 6: Run tests to confirm PASS**

```bash
pytest tests/api/test_artifacts_sp3b.py::test_get_artifacts_empty tests/api/test_artifacts_sp3b.py::test_get_artifacts_returns_latest -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/data/repositories/job_artifacts.py src/api/schemas/jobs.py src/api/routers/jobs.py tests/api/test_artifacts_sp3b.py
git commit -m "feat(backend): JobArtifactsRepository + GET /jobs/{id}/artifacts

- By Pravin Kamdi"
```

---

## Task 2: POST /jobs/{id}/tailor + implement tailor task

**Files:**
- Modify: `src/api/routers/jobs.py`
- Modify: `src/tasks/tailor.py`
- Modify: `tests/api/test_artifacts_sp3b.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/api/test_artifacts_sp3b.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_tailor_queues_task(async_client, redis_client, db_session):
    from unittest.mock import patch
    from src.data.models.job import Job
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Eng", company="Co",
              jd_text="jd", url=None)
    db_session.add(job)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    with patch("src.api.routers.jobs.run_tailor") as mock_task:
        mock_task.delay.return_value = None
        r = await async_client.post(
            f"/api/v1/jobs/{job.id}/tailor",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["queued"] is True
    mock_task.delay.assert_called_once()
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/api/test_artifacts_sp3b.py::test_trigger_tailor_queues_task -v
```

Expected: FAIL — `405` or `404`

- [ ] **Step 3: Add `POST /{job_id}/tailor` to `src/api/routers/jobs.py`**

Add this import at the top of `src/api/routers/jobs.py`:

```python
from src.tasks.tailor import run_tailor
```

Then append this route to the end of the file:

```python
@router.post("/{job_id}/tailor")
async def trigger_tailor(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    import uuid as _uuid
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    run_tailor.delay(correlation_id=str(_uuid.uuid4()), job_id=str(job_id))
    return {"queued": True}
```

- [ ] **Step 4: Run test to confirm PASS**

```bash
pytest tests/api/test_artifacts_sp3b.py::test_trigger_tailor_queues_task -v
```

Expected: PASS

- [ ] **Step 5: Implement `_tailor_for_job` in `src/tasks/tailor.py`**

Replace the full file content:

```python
"""Tailor stage wrapper. Generates resume/cover artifacts for one job."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="tailor", max_retries=2, queue="ai")
def run_tailor(*, correlation_id: str, job_id: str) -> dict:
    return _tailor_for_job(correlation_id, job_id)


def _tailor_for_job(correlation_id: str, job_id: str) -> dict:
    import json
    import uuid as _uuid
    from pathlib import Path

    from src.models import CandidateProfile, JobPosting
    from src.observability.logging import get_logger
    from src.resume.engine import ResumeService
    from src.tasks.base import _run_async
    from src.utils.config import load_config

    log = get_logger("tasks.tailor")
    config = load_config(Path("config.yaml"))

    profile_path = Path(config.app.profile_path)
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    with profile_path.open() as f:
        profile = CandidateProfile.model_validate(json.load(f))

    async def _load_job():
        from src.data.db import get_sessionmaker
        from src.data.repositories.jobs import JobsRepository
        maker = get_sessionmaker()
        async with maker() as session:
            return await JobsRepository(session).get_by_id(_uuid.UUID(job_id))

    job_row = _run_async(_load_job)
    if not job_row:
        raise ValueError(f"Job not found: {job_id}")

    job_posting = JobPosting(
        source=job_row.source,
        job_id=str(job_row.id),
        title=job_row.title,
        company=job_row.company,
        location=job_row.location or "",
        description=job_row.jd_text,
        url=job_row.url or "",
    )

    service = ResumeService(config.resume, Path("."), log)
    bundle, _ = service.build_assets(profile=profile, job=job_posting)

    async def _persist():
        from src.data.db import get_sessionmaker
        from src.data.repositories.job_artifacts import JobArtifactsRepository
        maker = get_sessionmaker()
        async with maker() as session:
            repo = JobArtifactsRepository(session)
            await repo.create(
                job_id=_uuid.UUID(job_id),
                kind="cover_letter",
                text=bundle.cover_letter,
            )
            await repo.create(
                job_id=_uuid.UUID(job_id),
                kind="resume_text",
                text=bundle.resume_text,
            )
            await session.commit()

    _run_async(_persist)
    return {"artifacts_written": 2, "job_id": job_id}
```

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/jobs.py src/tasks/tailor.py tests/api/test_artifacts_sp3b.py
git commit -m "feat(backend): POST /jobs/{id}/tailor + implement tailor task

- By Pravin Kamdi"
```

---

## Task 3: FCM kind enrichment

**Files:**
- Modify: `src/tasks/base.py`

This makes the FCM data payload include `kind` (the pipeline stage name) so Android can identify tailor-complete events. The `run_tailor` result dict already includes `job_id`, so FCM data will contain both `kind=tailor` and `job_id=<uuid>` after this change.

- [ ] **Step 1: Update `_push_on_complete` in `src/tasks/base.py`**

Find this block in `_push_on_complete` (around line 63–72):

```python
        svc = _build_push_service()
        body_parts = [f"Stage: {stage}"]
        for k, v in list(result.items())[:2]:
            body_parts.append(f"{k}: {v}")
        svc.send_event(PushEvent(
            title=f"Pipeline: {stage} complete",
            body=" | ".join(body_parts),
            data=result,
        ), tokens=tokens)
```

Replace with:

```python
        svc = _build_push_service()
        body_parts = [f"Stage: {stage}"]
        for k, v in list(result.items())[:2]:
            body_parts.append(f"{k}: {v}")
        svc.send_event(PushEvent(
            title=f"Pipeline: {stage} complete",
            body=" | ".join(body_parts),
            data={"kind": stage, **result},
        ), tokens=tokens)
```

- [ ] **Step 2: Verify existing push tests still pass**

```bash
pytest tests/api/test_notifications.py -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add src/tasks/base.py
git commit -m "feat(backend): add kind to FCM push data payload

- By Pravin Kamdi"
```

---

## Task 4: ApplicationOut briefing_json + POST /applications/{id}/brief

**Files:**
- Modify: `src/api/schemas/applications.py`
- Modify: `src/api/routers/applications.py`
- Modify: `tests/api/test_artifacts_sp3b.py`

- [ ] **Step 1: Add three failing tests**

Append to `tests/api/test_artifacts_sp3b.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_application_out_has_briefing_json(async_client, redis_client, db_session):
    from src.data.models.application import Application
    briefing = [{"question": "Q1", "rationale": "R1", "star_points": ["S1", "S2"]}]
    app = Application(
        job_id=uuid.uuid4(),
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=json.dumps(briefing),
    )
    db_session.add(app)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    target = next((i for i in items if i["id"] == str(app.id)), None)
    assert target is not None
    assert isinstance(target["briefing_json"], list)
    assert target["briefing_json"][0]["question"] == "Q1"
    assert target["briefing_json"][0]["star_points"] == ["S1", "S2"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_brief_stores_and_returns(async_client, redis_client, db_session):
    from unittest.mock import MagicMock, mock_open, patch
    from src.data.models.application import Application
    from src.data.models.job import Job

    job = Job(source="test", source_id=str(uuid.uuid4()), title="SWE", company="Acme",
              jd_text="Build systems", url=None)
    db_session.add(job)
    await db_session.flush()

    app = Application(
        job_id=job.id,
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=None,
    )
    db_session.add(app)
    await db_session.commit()

    mock_profile = {
        "name": "Test User", "email": "t@t.com", "phone": "555",
        "location": "Remote", "headline": "Eng", "summary": "Eng",
        "skills": [], "experience": [], "education": [], "projects": [], "certifications": [],
    }
    fake_briefing = [{"question": "Q?", "rationale": "Because", "star_points": ["S1", "S2"]}]
    mock_cfg = MagicMock()
    mock_cfg.resume = MagicMock()
    mock_cfg.app.profile_path = "data/profile.json"

    token = await _get_token(async_client, redis_client)
    with patch("src.utils.config.load_config", return_value=mock_cfg), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.open", mock_open(read_data=json.dumps(mock_profile))), \
         patch("src.resume.engine.ResumeService") as MockSvc:
        MockSvc.return_value.generate_interview_briefing.return_value = fake_briefing
        r = await async_client.post(
            f"/api/v1/applications/{app.id}/brief",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["briefing_json"], list)
    assert data["briefing_json"][0]["question"] == "Q?"
    assert data["briefing_json"][0]["star_points"] == ["S1", "S2"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_brief_idempotent(async_client, redis_client, db_session):
    from unittest.mock import patch
    from src.data.models.application import Application

    existing = [{"question": "Existing?", "rationale": "R", "star_points": ["S"]}]
    app = Application(
        job_id=uuid.uuid4(),
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=json.dumps(existing),
    )
    db_session.add(app)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    with patch("src.resume.engine.ResumeService") as MockSvc:
        r = await async_client.post(
            f"/api/v1/applications/{app.id}/brief",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    assert r.json()["briefing_json"][0]["question"] == "Existing?"
    MockSvc.return_value.generate_interview_briefing.assert_not_called()
```

Also add these imports at the top of the test file (after the existing ones):

```python
from datetime import UTC, datetime
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/api/test_artifacts_sp3b.py::test_application_out_has_briefing_json tests/api/test_artifacts_sp3b.py::test_generate_brief_stores_and_returns tests/api/test_artifacts_sp3b.py::test_generate_brief_idempotent -v
```

Expected: FAIL — `briefing_json` missing from response / `404` on brief endpoint

- [ ] **Step 3: Replace `src/api/schemas/applications.py`**

```python
from __future__ import annotations

import json
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class BriefingItem(BaseModel):
    question: str
    rationale: str
    star_points: list[str]


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    channel: str
    current_status: str
    submitted_at: datetime
    external_ref: str | None
    briefing_json: list[BriefingItem] | None = None

    model_config = {"from_attributes": True}

    @field_validator("briefing_json", mode="before")
    @classmethod
    def parse_briefing(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v
```

- [ ] **Step 4: Add `POST /{app_id}/brief` to `src/api/routers/applications.py`**

Replace the full file:

```python
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.applications import ApplicationOut
from src.api.schemas.common import PaginatedResponse
from src.data.db import get_sessionmaker
from src.data.repositories.applications import ApplicationsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[ApplicationOut])
async def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = ApplicationsRepository(db)
    items, total = await repo.list_paginated(page=page, per_page=per_page, status=status)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             has_next=(page * per_page) < total)


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: uuid.UUID, _device=Depends(get_current_device), db=Depends(_get_db),
):
    app = await ApplicationsRepository(db).get_by_id(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app


@router.post("/{app_id}/brief", response_model=ApplicationOut)
async def generate_brief(
    app_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    from src.models import CandidateProfile, JobPosting
    from src.observability.logging import get_logger
    from src.resume.engine import ResumeService
    from src.utils.config import load_config
    from src.data.repositories.jobs import JobsRepository

    app = await ApplicationsRepository(db).get_by_id(app_id)
    if not app:
        raise HTTPException(404, "Application not found")

    if app.briefing_json:
        return app

    config = load_config(Path("config.yaml"))
    profile_path = Path(config.app.profile_path)
    if not profile_path.exists():
        raise HTTPException(422, detail="Resume not configured")

    job_row = await JobsRepository(db).get_by_id(app.job_id)
    if not job_row:
        raise HTTPException(404, "Job not found")

    with profile_path.open() as f:
        profile = CandidateProfile.model_validate(json.load(f))

    job_posting = JobPosting(
        source=job_row.source,
        job_id=str(job_row.id),
        title=job_row.title,
        company=job_row.company,
        location=job_row.location or "",
        description=job_row.jd_text,
        url=job_row.url or "",
    )

    service = ResumeService(config.resume, Path("."), get_logger("api.brief"))
    briefing = await asyncio.get_event_loop().run_in_executor(
        None, service.generate_interview_briefing, profile, job_posting
    )

    app.briefing_json = json.dumps(briefing)
    await db.commit()
    await db.refresh(app)
    return app
```

- [ ] **Step 5: Run all six tests**

```bash
pytest tests/api/test_artifacts_sp3b.py -v
```

Expected: all 6 PASS

- [ ] **Step 6: Run existing application and job tests to check no regressions**

```bash
pytest tests/api/test_applications.py tests/api/test_jobs.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas/applications.py src/api/routers/applications.py tests/api/test_artifacts_sp3b.py
git commit -m "feat(backend): ApplicationOut.briefing_json + POST /applications/{id}/brief

- By Pravin Kamdi"
```

---

## Task 5: Android DTOs

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/core/api/JobAiService.kt`

No compilation check possible (Android SDK not installed). Verify by code review.

- [ ] **Step 1: Add new DTOs and update `ApplicationDto`**

In `JobAiService.kt`, the current `ApplicationDto` is:

```kotlin
@JsonClass(generateAdapter = true)
data class ApplicationDto(
    val id: String,
    @Json(name = "job_id") val jobId: String,
    val channel: String,
    @Json(name = "current_status") val currentStatus: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "external_ref") val externalRef: String?,
)
```

Replace it with:

```kotlin
@JsonClass(generateAdapter = true)
data class BriefingItemDto(
    val question: String,
    val rationale: String,
    @Json(name = "star_points") val starPoints: List<String>,
)

@JsonClass(generateAdapter = true)
data class ApplicationDto(
    val id: String,
    @Json(name = "job_id") val jobId: String,
    val channel: String,
    @Json(name = "current_status") val currentStatus: String,
    @Json(name = "submitted_at") val submittedAt: String,
    @Json(name = "external_ref") val externalRef: String?,
    @Json(name = "briefing_json") val briefingJson: List<BriefingItemDto>? = null,
)
```

After the existing DLQ DTOs block (after `DlqActionOut`), add:

```kotlin
@JsonClass(generateAdapter = true)
data class ArtifactsDto(
    @Json(name = "cover_letter") val coverLetter: String?,
    @Json(name = "resume_text") val resumeText: String?,
    @Json(name = "generated_at") val generatedAt: String?,
)

@JsonClass(generateAdapter = true)
data class TailorQueuedDto(val queued: Boolean)
```

In the `JobAiService` interface, add these four methods after `triggerRun()`:

```kotlin
@GET("jobs/{id}/artifacts")
suspend fun getArtifacts(@Path("id") id: String): ArtifactsDto

@POST("jobs/{id}/tailor")
suspend fun triggerTailor(@Path("id") id: String): TailorQueuedDto

@GET("applications/{id}")
suspend fun getApplication(@Path("id") id: String): ApplicationDto

@POST("applications/{id}/brief")
suspend fun generateBrief(@Path("id") id: String): ApplicationDto
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/core/api/JobAiService.kt
git commit -m "feat(android): add ArtifactsDto, TailorQueuedDto, BriefingItemDto DTOs + 4 new API methods

- By Pravin Kamdi"
```

---

## Task 6: FcmEventBus + update JobAiFirebaseService

**Files:**
- Create: `android/app/src/main/java/com/jobai/companion/firebase/FcmEventBus.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/firebase/JobAiFirebaseService.kt`

- [ ] **Step 1: Create `FcmEventBus.kt`**

```kotlin
package com.jobai.companion.firebase

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

data class FcmEvent(val kind: String, val jobId: String?)

object FcmEventBus {
    private val _events = MutableSharedFlow<FcmEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<FcmEvent> = _events.asSharedFlow()
    fun emit(event: FcmEvent) { _events.tryEmit(event) }
}
```

- [ ] **Step 2: Update `onMessageReceived` in `JobAiFirebaseService.kt`**

Replace the current `onMessageReceived` method:

```kotlin
override fun onMessageReceived(message: RemoteMessage) {
    val title = message.notification?.title ?: message.data["title"] ?: "JobAI"
    val body = message.notification?.body ?: message.data["body"] ?: ""
    showNotification(title, body)
}
```

With:

```kotlin
override fun onMessageReceived(message: RemoteMessage) {
    val kind = message.data["kind"]
    val jobId = message.data["job_id"]
    if (kind != null) {
        FcmEventBus.emit(FcmEvent(kind = kind, jobId = jobId))
    }
    val title = message.notification?.title ?: message.data["title"] ?: "JobAI"
    val body = message.notification?.body ?: message.data["body"] ?: ""
    showNotification(title, body)
}
```

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/firebase/FcmEventBus.kt \
        android/app/src/main/java/com/jobai/companion/firebase/JobAiFirebaseService.kt
git commit -m "feat(android): FcmEventBus singleton + emit tailor events in JobAiFirebaseService

- By Pravin Kamdi"
```

---

## Task 7: JobDetailViewModel + JobDetailScreen

**Files:**
- Create: `android/app/src/main/java/com/jobai/companion/jobs/JobDetailViewModel.kt`
- Create: `android/app/src/main/java/com/jobai/companion/jobs/JobDetailScreen.kt`

- [ ] **Step 1: Create `JobDetailViewModel.kt`**

```kotlin
package com.jobai.companion.jobs

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.firebase.FcmEventBus
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class JobDetailUiState(
    val jobId: String = "",
    val title: String = "",
    val company: String = "",
    val coverLetter: String? = null,
    val resumeText: String? = null,
    val isLoading: Boolean = true,
    val isGenerating: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class JobDetailViewModel @Inject constructor(
    private val api: JobAiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val jobId: String = checkNotNull(savedStateHandle["jobId"])

    private val _state = MutableStateFlow(
        JobDetailUiState(
            jobId = jobId,
            title = savedStateHandle["title"] ?: "",
            company = savedStateHandle["company"] ?: "",
        )
    )
    val uiState: StateFlow<JobDetailUiState> = _state.asStateFlow()

    init {
        loadArtifacts()
        viewModelScope.launch {
            FcmEventBus.events
                .filter { it.kind == "tailor" && it.jobId == jobId }
                .collect { loadArtifacts() }
        }
    }

    fun loadArtifacts() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { api.getArtifacts(jobId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            coverLetter = dto.coverLetter,
                            resumeText = dto.resumeText,
                            isLoading = false,
                            isGenerating = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isLoading = false, error = err.message) }
                }
        }
    }

    fun triggerGeneration() {
        viewModelScope.launch {
            _state.update { it.copy(isGenerating = true, error = null) }
            runCatching { api.triggerTailor(jobId) }
                .onFailure { err ->
                    _state.update { it.copy(isGenerating = false, error = err.message) }
                }
            // FcmEventBus.events collector above calls loadArtifacts() when tailor completes
        }
    }
}
```

- [ ] **Step 2: Create `JobDetailScreen.kt`**

```kotlin
package com.jobai.companion.jobs

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.ui.theme.AppTypography
import com.jobai.companion.core.ui.theme.Background
import com.jobai.companion.core.ui.theme.Primary
import com.jobai.companion.core.ui.theme.Surface
import com.jobai.companion.core.ui.theme.TextDisabled
import com.jobai.companion.core.ui.theme.TextMuted
import com.jobai.companion.core.ui.theme.TextPrimary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    onBack: () -> Unit,
    vm: JobDetailViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(state.title, style = AppTypography.titleMedium, color = TextPrimary)
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .background(Background)
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(state.company, style = AppTypography.bodyLarge, color = TextMuted)

            if (state.isLoading) {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Primary)
                }
            } else {
                ArtifactSection(
                    title = "Cover Letter",
                    content = state.coverLetter,
                    isGenerating = state.isGenerating,
                    onGenerate = { vm.triggerGeneration() },
                )
                HorizontalDivider()
                ArtifactSection(
                    title = "Tailored Resume",
                    content = state.resumeText,
                    isGenerating = state.isGenerating,
                    onGenerate = null,
                )
                state.error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, style = AppTypography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun ArtifactSection(
    title: String,
    content: String?,
    isGenerating: Boolean,
    onGenerate: (() -> Unit)?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = AppTypography.titleSmall, color = TextPrimary)
        when {
            content != null -> Card(
                shape = RoundedCornerShape(8.dp),
                colors = CardDefaults.cardColors(containerColor = Surface),
            ) {
                Text(
                    content,
                    modifier = Modifier.padding(12.dp),
                    style = AppTypography.bodySmall,
                    color = TextMuted,
                )
            }
            isGenerating -> Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    color = Primary,
                    strokeWidth = 2.dp,
                )
                Text("Generating…", style = AppTypography.bodySmall, color = TextMuted)
            }
            onGenerate != null -> Button(onClick = onGenerate) { Text("Generate") }
            else -> Text("Not yet generated", style = AppTypography.bodySmall, color = TextDisabled)
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/jobs/JobDetailViewModel.kt \
        android/app/src/main/java/com/jobai/companion/jobs/JobDetailScreen.kt
git commit -m "feat(android): JobDetailScreen — cover letter + resume text with generate trigger

- By Pravin Kamdi"
```

---

## Task 8: ApplicationDetailViewModel + ApplicationDetailScreen

**Files:**
- Create: `android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailViewModel.kt`
- Create: `android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailScreen.kt`

- [ ] **Step 1: Create `ApplicationDetailViewModel.kt`**

```kotlin
package com.jobai.companion.tracker

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jobai.companion.core.api.BriefingItemDto
import com.jobai.companion.core.api.JobAiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AppDetailUiState(
    val appId: String = "",
    val title: String = "",
    val currentStatus: String = "",
    val briefingItems: List<BriefingItemDto> = emptyList(),
    val isLoading: Boolean = true,
    val isGenerating: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ApplicationDetailViewModel @Inject constructor(
    private val api: JobAiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val appId: String = checkNotNull(savedStateHandle["appId"])

    private val _state = MutableStateFlow(
        AppDetailUiState(
            appId = appId,
            title = savedStateHandle["title"] ?: "",
            currentStatus = savedStateHandle["status"] ?: "",
        )
    )
    val uiState: StateFlow<AppDetailUiState> = _state.asStateFlow()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { api.getApplication(appId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            briefingItems = dto.briefingJson ?: emptyList(),
                            isLoading = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isLoading = false, error = err.message) }
                }
        }
    }

    fun generateBrief() {
        viewModelScope.launch {
            _state.update { it.copy(isGenerating = true, error = null) }
            runCatching { api.generateBrief(appId) }
                .onSuccess { dto ->
                    _state.update {
                        it.copy(
                            briefingItems = dto.briefingJson ?: emptyList(),
                            isGenerating = false,
                        )
                    }
                }
                .onFailure { err ->
                    _state.update { it.copy(isGenerating = false, error = err.message) }
                }
        }
    }
}
```

- [ ] **Step 2: Create `ApplicationDetailScreen.kt`**

```kotlin
package com.jobai.companion.tracker

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jobai.companion.core.api.BriefingItemDto
import com.jobai.companion.core.ui.components.StatusBadge
import com.jobai.companion.core.ui.theme.AppTypography
import com.jobai.companion.core.ui.theme.Background
import com.jobai.companion.core.ui.theme.Primary
import com.jobai.companion.core.ui.theme.Surface
import com.jobai.companion.core.ui.theme.TextMuted
import com.jobai.companion.core.ui.theme.TextPrimary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApplicationDetailScreen(
    onBack: () -> Unit,
    vm: ApplicationDetailViewModel = hiltViewModel(),
) {
    val state by vm.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        state.title.ifBlank { "Application" },
                        style = AppTypography.titleMedium,
                        color = TextPrimary,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        }
    ) { padding ->
        if (state.isLoading) {
            Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator(color = Primary)
            }
        } else {
            LazyColumn(
                Modifier
                    .fillMaxSize()
                    .background(Background)
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item { StatusBadge(state.currentStatus) }
                item {
                    Text("Interview Prep", style = AppTypography.titleMedium, color = TextPrimary)
                }
                if (state.briefingItems.isEmpty()) {
                    item {
                        if (state.isGenerating) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = Primary,
                                )
                                Text("Generating…", style = AppTypography.bodyMedium, color = TextMuted)
                            }
                        } else {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(
                                    "No interview brief yet.",
                                    style = AppTypography.bodyMedium,
                                    color = TextMuted,
                                )
                                Button(onClick = { vm.generateBrief() }) {
                                    Text("Generate Interview Brief")
                                }
                            }
                        }
                    }
                } else {
                    items(state.briefingItems) { item -> BriefingCard(item) }
                }
                state.error?.let {
                    item {
                        Text(it, color = MaterialTheme.colorScheme.error, style = AppTypography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BriefingCard(item: BriefingItemDto) {
    var expanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        onClick = { expanded = !expanded },
    ) {
        Column(
            Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(item.question, style = AppTypography.titleSmall, color = TextPrimary)
            Text(item.rationale, style = AppTypography.bodySmall, color = TextMuted)
            if (expanded) {
                HorizontalDivider(Modifier.padding(vertical = 4.dp))
                item.starPoints.forEach { point ->
                    Text("• $point", style = AppTypography.bodySmall, color = TextPrimary)
                }
            }
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailViewModel.kt \
        android/app/src/main/java/com/jobai/companion/tracker/ApplicationDetailScreen.kt
git commit -m "feat(android): ApplicationDetailScreen — interview prep brief with generate trigger

- By Pravin Kamdi"
```

---

## Task 9: Navigation wiring + make job/app cards clickable

**Files:**
- Modify: `android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/jobs/JobsScreen.kt`
- Modify: `android/app/src/main/java/com/jobai/companion/tracker/TrackerScreen.kt`

- [ ] **Step 1: Add `Screen.JobDetail` and `Screen.AppDetail` in `AppNavigation.kt`**

In the `sealed class Screen` block (after `object Dlq : Screen("dlq")`), add:

```kotlin
object JobDetail : Screen("job_detail/{jobId}/{title}/{company}") {
    fun route(jobId: String, title: String, company: String) =
        "job_detail/${jobId}/${android.net.Uri.encode(title)}/${android.net.Uri.encode(company)}"
}

object AppDetail : Screen("app_detail/{appId}/{title}/{status}") {
    fun route(appId: String, title: String, status: String) =
        "app_detail/${appId}/${android.net.Uri.encode(title)}/${android.net.Uri.encode(status)}"
}
```

- [ ] **Step 2: Import new screens and add composable routes in `AppNavigation.kt`**

Add imports at the top (with the other screen imports):

```kotlin
import androidx.navigation.NavType
import androidx.navigation.navArgument
import com.jobai.companion.jobs.JobDetailScreen
import com.jobai.companion.tracker.ApplicationDetailScreen
```

Inside the `NavHost` block (after the existing `composable(Screen.Dlq.route)` entry), add:

```kotlin
composable(
    Screen.JobDetail.route,
    arguments = listOf(
        navArgument("jobId") { type = NavType.StringType },
        navArgument("title") { type = NavType.StringType },
        navArgument("company") { type = NavType.StringType },
    )
) {
    JobDetailScreen(onBack = { navController.popBackStack() })
}

composable(
    Screen.AppDetail.route,
    arguments = listOf(
        navArgument("appId") { type = NavType.StringType },
        navArgument("title") { type = NavType.StringType },
        navArgument("status") { type = NavType.StringType },
    )
) {
    ApplicationDetailScreen(onBack = { navController.popBackStack() })
}
```

- [ ] **Step 3: Update `JobsScreen` composable call in `AppNavigation.kt`**

Find:

```kotlin
composable(Screen.Jobs.route) { JobsScreen() }
```

Replace with:

```kotlin
composable(Screen.Jobs.route) {
    JobsScreen(
        onJobClick = { job ->
            navController.navigate(Screen.JobDetail.route(job.id, job.title, job.company))
        }
    )
}
```

- [ ] **Step 4: Update `TrackerScreen` composable call in `AppNavigation.kt`**

Find:

```kotlin
composable(Screen.Tracker.route) { TrackerScreen() }
```

Replace with:

```kotlin
composable(Screen.Tracker.route) {
    TrackerScreen(
        onAppClick = { app ->
            navController.navigate(
                Screen.AppDetail.route(app.id, app.jobTitle.ifBlank { "Application" }, app.currentStatus)
            )
        }
    )
}
```

- [ ] **Step 5: Update `JobsScreen.kt` to accept and use `onJobClick`**

Replace the full `JobsScreen` composable signature and the `items` block.

Current:
```kotlin
@Composable
fun JobsScreen(vm: JobsViewModel = hiltViewModel()) {
```

Replace with:
```kotlin
@Composable
fun JobsScreen(
    onJobClick: (com.jobai.companion.core.model.Job) -> Unit = {},
    vm: JobsViewModel = hiltViewModel(),
) {
```

Add `foundation.clickable` import at the top of the file:
```kotlin
import androidx.compose.foundation.clickable
```

Find the `items` block:

```kotlin
items(state.jobs, key = { it.id }) { job ->
    JobCard(
        job = job,
        onStar = { vm.star(job.id) },
        onDismiss = { vm.dismiss(job.id) },
    )
}
```

Replace with:

```kotlin
items(state.jobs, key = { it.id }) { job ->
    Box(Modifier.clickable { onJobClick(job) }) {
        JobCard(
            job = job,
            onStar = { vm.star(job.id) },
            onDismiss = { vm.dismiss(job.id) },
        )
    }
}
```

Also add `import androidx.compose.foundation.layout.Box` to the imports (it's already imported via the wildcard `androidx.compose.foundation.layout.*` — check the existing imports; if the wildcard is present, no change needed).

- [ ] **Step 6: Update `TrackerScreen.kt` to accept and use `onAppClick`**

Replace the `TrackerScreen` composable signature:

Current:
```kotlin
@Composable
fun TrackerScreen(vm: TrackerViewModel = hiltViewModel()) {
```

Replace with:
```kotlin
@Composable
fun TrackerScreen(
    onAppClick: (com.jobai.companion.core.model.Application) -> Unit = {},
    vm: TrackerViewModel = hiltViewModel(),
) {
```

Add `foundation.clickable` import:
```kotlin
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
```

Find the `items` block in `TrackerScreen`:

```kotlin
items(state.applications, key = { it.id }) { app ->
    ApplicationCard(app)
}
```

Replace with:

```kotlin
items(state.applications, key = { it.id }) { app ->
    Box(Modifier.clickable { onAppClick(app) }) {
        ApplicationCard(app)
    }
}
```

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/java/com/jobai/companion/navigation/AppNavigation.kt \
        android/app/src/main/java/com/jobai/companion/jobs/JobsScreen.kt \
        android/app/src/main/java/com/jobai/companion/tracker/TrackerScreen.kt
git commit -m "feat(android): wire JobDetail + AppDetail routes, make job/app cards clickable

- By Pravin Kamdi"
```

---

## Regression check

After all tasks complete, run the full backend test suite to verify no regressions:

```bash
pytest tests/api/ -v --ignore=tests/api/test_pipeline.py
```

Expected: all existing tests PASS, all 6 new `test_artifacts_sp3b.py` tests PASS.
