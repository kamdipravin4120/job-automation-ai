from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RunOut(BaseModel):
    id: uuid.UUID
    kind: str
    correlation_id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_details: dict | None = None
    steps: list = Field(default_factory=list)
    jobs_found: int = 0

    model_config = {"from_attributes": True}
