"""Tailor stage wrapper. Generates resume/cover/pitch artifacts for one job."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="tailor", max_retries=2, queue="ai")
def run_tailor(*, correlation_id: str, job_id: str) -> dict:
    return _tailor_for_job(correlation_id, job_id)


def _tailor_for_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.observability.logging import get_logger
    from src.resume.engine import ResumeService
    from src.utils.config import load_config

    log = get_logger("tasks.tailor")
    config = load_config(Path("config.yaml"))
    service = ResumeService(config.resume, Path("."), log)
    artifacts = service.tailor_for_job_id(job_id=job_id)
    return {"artifacts_written": len(artifacts)}
