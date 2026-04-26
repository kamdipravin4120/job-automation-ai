from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class IntegrationOut(BaseModel):
    provider: str
    status: str
    last_error: str | None = None
    last_check_at: datetime | None = None

    model_config = {"from_attributes": True}
