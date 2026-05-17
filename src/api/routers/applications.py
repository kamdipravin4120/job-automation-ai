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
from src.data.models.application import Application
from src.data.models.job import Job
from src.data.repositories.applications import ApplicationsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


def _to_out(app: Application, job: Job | None) -> ApplicationOut:
    return ApplicationOut.model_validate({
        "id": app.id,
        "job_id": app.job_id,
        "job_title": job.title if job else "",
        "job_company": job.company if job else "",
        "channel": app.channel,
        "current_status": app.current_status,
        "submitted_at": app.submitted_at,
        "external_ref": app.external_ref,
        "recruiter": app.recruiter,
        "email_status": app.email_status,
        "last_contact_at": app.last_contact_at,
        "next_follow_up_at": app.next_follow_up_at,
        "briefing_json": app.briefing_json,
    })


@router.get("/follow-ups", response_model=list[ApplicationOut])
async def list_follow_ups(_device=Depends(get_current_device), db=Depends(_get_db)):
    rows = await ApplicationsRepository(db).list_follow_ups()
    return [_to_out(app, job) for app, job in rows]


@router.get("", response_model=PaginatedResponse[ApplicationOut])
async def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = ApplicationsRepository(db)
    rows, total = await repo.list_paginated_with_jobs(page=page, per_page=per_page, status=status)
    items = [_to_out(app, job) for app, job in rows]
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             has_next=(page * per_page) < total)


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: uuid.UUID, _device=Depends(get_current_device), db=Depends(_get_db),
):
    row = await ApplicationsRepository(db).get_by_id_with_job(app_id)
    if not row:
        raise HTTPException(404, "Application not found")
    return _to_out(row[0], row[1])


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

    row = await ApplicationsRepository(db).get_by_id_with_job(app_id)
    if not row:
        raise HTTPException(404, "Application not found")
    app, job_row = row

    if app.briefing_json is not None:
        return _to_out(app, job_row)

    config = load_config(Path("config.yaml"))
    profile_path = Path(config.app.profile_path)
    if not profile_path.exists():
        raise HTTPException(422, detail="Resume not configured")

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
    briefing = await asyncio.get_running_loop().run_in_executor(
        None, service.generate_interview_briefing, profile, job_posting
    )

    app.briefing_json = json.dumps(briefing)
    await db.commit()
    await db.refresh(app)
    return _to_out(app, job_row)
