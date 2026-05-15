from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.core.deps import get_current_device
from src.api.schemas.common import PaginatedResponse
from src.api.schemas.jobs import ArtifactsOut, JobOut
from src.data.db import get_sessionmaker
from src.data.models.job import Job
from src.data.repositories.job_artifacts import JobArtifactsRepository
from src.data.repositories.jobs import JobsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=PaginatedResponse[JobOut])
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    source: str | None = Query(None),
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = JobsRepository(db)
    items, total = await repo.list_paginated(
        page=page, per_page=per_page, status=status, source=source
    )
    return PaginatedResponse(
        items=items, total=total, page=page, per_page=per_page,
        has_next=(page * per_page) < total,
    )


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = JobsRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/star", response_model=JobOut)
async def star_job(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.starred = not job.starred
    await db.commit()
    try:
        await db.refresh(job)
    except Exception:
        pass
    return JobOut.model_validate(job)


@router.post("/{job_id}/dismiss", response_model=JobOut)
async def dismiss_job(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.dismissed = True
    await db.commit()
    try:
        await db.refresh(job)
    except Exception:
        pass
    return JobOut.model_validate(job)


@router.get("/{job_id}/artifacts", response_model=ArtifactsOut)
async def get_job_artifacts(
    job_id: uuid.UUID,
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    repo = JobArtifactsRepository(db)
    cover = await repo.get_latest(job_id, "cover_letter")
    resume_art = await repo.get_latest(job_id, "resume_text")
    return ArtifactsOut(
        cover_letter=cover.text if cover else None,
        resume_text=resume_art.text if resume_art else None,
        generated_at=(cover or resume_art).generated_at if (cover or resume_art) else None,
    )
