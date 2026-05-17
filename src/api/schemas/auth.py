from pydantic import BaseModel, field_validator


class ChallengeRequest(BaseModel):
    bootstrap_secret: str

    @field_validator("bootstrap_secret")
    @classmethod
    def must_be_64_hex(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("bootstrap_secret must be a 64-character hex string")
        return v.lower()


class ChallengeResponse(BaseModel):
    challenge: str


class PairRequest(BaseModel):
    bootstrap_secret: str
    public_key: str
    signature: str

    @field_validator("bootstrap_secret")
    @classmethod
    def must_be_64_hex(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("bootstrap_secret must be a 64-character hex string")
        return v.lower()


class TokenResponse(BaseModel):
    token: str


class ReauthChallengeRequest(BaseModel):
    device_id: str


class ReauthRequest(BaseModel):
    device_id: str
    signature: str
