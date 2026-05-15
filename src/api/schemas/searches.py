from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchIn(BaseModel):
    keywords: str
    location: str
    sources: list[str] = Field(default_factory=list)
    min_match_score: float = 0.6
    enabled: bool = True
    run_every_hours: int = 24


class SearchPatch(BaseModel):
    keywords: str | None = None
    location: str | None = None
    sources: list[str] | None = None
    min_match_score: float | None = None
    enabled: bool | None = None
    run_every_hours: int | None = None


class SearchOut(BaseModel):
    id: uuid.UUID
    keywords: str
    location: str
    sources: list[str]
    min_match_score: float
    enabled: bool
    run_every_hours: int
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
