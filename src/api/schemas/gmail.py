from __future__ import annotations
from pydantic import BaseModel


class GmailStatusOut(BaseModel):
    authorized: bool


class OAuthInitOut(BaseModel):
    user_code: str
    verification_url: str
    expires_in: int


class OAuthPollOut(BaseModel):
    status: str  # "pending" | "authorized"


class SyncOut(BaseModel):
    processed: int
    classified: dict[str, int]
