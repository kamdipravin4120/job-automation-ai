from pydantic import BaseModel


class TriggerRequest(BaseModel):
    correlation_id: str | None = None


class TriggerResponse(BaseModel):
    correlation_id: str
    queued: bool
