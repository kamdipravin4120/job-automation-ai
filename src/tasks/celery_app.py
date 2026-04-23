from __future__ import annotations

from celery import Celery
from kombu import Queue

from src.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "job_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.tasks.scrape",
        "src.tasks.match",
        "src.tasks.tailor",
        "src.tasks.apply",
    ],
)

celery_app.conf.update(
    task_acks_late=True,            # requeue on worker crash
    worker_prefetch_multiplier=1,   # one task per worker at a time, fair for long jobs
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
    task_queues=(
        Queue("scrape"),
        Queue("ai"),
        Queue("browser"),
        Queue("mail"),
    ),
    task_default_queue="scrape",
    task_routes={
        "src.tasks.scrape.*": {"queue": "scrape"},
        "src.tasks.match.*": {"queue": "ai"},
        "src.tasks.tailor.*": {"queue": "ai"},
        "src.tasks.apply.*": {"queue": "browser"},
    },
)
