from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SelectorOverrideOut(BaseModel):
    id: uuid.UUID
    source: str
    key_path: str
    selector: str
    proposed_at: datetime
    proposed_by: str
    status: str
    dom_snapshot_path: str | None = None
    provenance: dict | None = None

    model_config = {"from_attributes": True}
