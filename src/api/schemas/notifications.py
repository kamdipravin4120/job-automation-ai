from pydantic import BaseModel


class FcmRegisterRequest(BaseModel):
    fcm_token: str


class FcmRegisterOut(BaseModel):
    registered: bool


class FcmUnregisterOut(BaseModel):
    unregistered: bool
