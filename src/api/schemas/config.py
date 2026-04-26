from __future__ import annotations

from pydantic import BaseModel


class ConfigOut(BaseModel):
    yaml_text: str


class ConfigUpdateRequest(BaseModel):
    yaml_text: str
