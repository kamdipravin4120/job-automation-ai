from pydantic import BaseModel


class ChallengeRequest(BaseModel):
    bootstrap_secret: str


class ChallengeResponse(BaseModel):
    challenge: str  # hex-encoded random bytes


class PairRequest(BaseModel):
    bootstrap_secret: str
    public_key: str    # PEM string
    signature: str     # hex-encoded Ed25519 signature over challenge bytes


class TokenResponse(BaseModel):
    token: str
