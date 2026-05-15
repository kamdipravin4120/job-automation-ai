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
