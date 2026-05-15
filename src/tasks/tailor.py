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
