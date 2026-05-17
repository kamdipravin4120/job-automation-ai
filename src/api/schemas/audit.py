from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    actor: str
    action: str
    target: str
    details: dict | None = None

    model_config = {"from_attributes": True}
