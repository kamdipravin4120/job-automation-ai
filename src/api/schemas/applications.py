from __future__ import annotations

import json
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class BriefingItem(BaseModel):
    question: str
    rationale: str
    star_points: list[str]


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str = ""
    job_company: str = ""
    channel: str
    current_status: str
    submitted_at: datetime
    external_ref: str | None
    recruiter: dict | None = None
    email_status: str | None = None
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    briefing_json: list[BriefingItem] | None = None

    model_config = {"from_attributes": False}

    @field_validator("briefing_json", mode="before")
    @classmethod
    def parse_briefing(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v
