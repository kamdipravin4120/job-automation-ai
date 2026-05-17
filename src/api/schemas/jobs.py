from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobOut(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    company: str
    url: str | None
    status: str
    match_score: float | None
    scraped_at: datetime
    location: str | None
    starred: bool
    dismissed: bool

    model_config = {"from_attributes": True}


class ArtifactsOut(BaseModel):
    cover_letter: str | None = None
    resume_text: str | None = None
    generated_at: datetime | None = None
