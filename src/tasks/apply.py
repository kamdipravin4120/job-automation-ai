"""Apply stage wrapper — Celery task that runs LinkedInEasyApplyBot for a single job."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="apply", max_retries=1, queue="browser")
def run_apply(*, correlation_id: str, job_id: str) -> dict:
    return _apply_to_job(correlation_id, job_id)


def _apply_to_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.apply.linkedin_easy_apply import LinkedInEasyApplyBot
    from src.models import ApplicationRecord
    from src.observability.logging import get_logger
    from src.utils.config import load_config

    log = get_logger("tasks.apply")
    config = load_config(Path("config.yaml"))
    flow = LinkedInEasyApplyBot(config, Path("."), log)

    record = ApplicationRecord(job_id=job_id)
    results = flow.apply([record], limit=1)
    submitted = any(r.status == "applied" for r in results)
    return {"submitted": submitted}
