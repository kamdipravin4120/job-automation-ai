from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.pipeline import TriggerRequest, TriggerResponse

router = APIRouter()


@router.post("/trigger", response_model=TriggerResponse, status_code=202)
async def trigger_pipeline(
    body: TriggerRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    _device=Depends(get_current_device),
):
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header required")

    correlation_id = body.correlation_id or str(uuid.uuid4())

    # Import deferred: src.tasks.scrape triggers Celery app init (get_settings) at module
    # load time, which requires DB/broker env vars unavailable at import time in tests.
    # task_id ties Celery deduplication to the idempotency key so replays after
    # the HTTP cache window (24h) don't enqueue a second task at the broker level.
    from src.tasks.scrape import run_scrape
    run_scrape.apply_async(kwargs={"correlation_id": correlation_id}, task_id=idempotency_key)

    return TriggerResponse(correlation_id=correlation_id, queued=True)
