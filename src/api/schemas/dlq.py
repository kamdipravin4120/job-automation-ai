from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DLQItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    correlation_id: str
    status: str
    error_code: str | None = None
    error_details: dict | None = None
    retry_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
