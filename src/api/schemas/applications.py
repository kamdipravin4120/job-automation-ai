from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    channel: str
    current_status: str
    submitted_at: datetime
    external_ref: str | None

    model_config = {"from_attributes": True}
