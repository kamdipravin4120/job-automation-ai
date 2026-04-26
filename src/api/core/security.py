from __future__ import annotations

import time
import uuid

import jwt as pyjwt
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)

from src.settings import get_settings


def create_jwt(device_id: uuid.UUID, *, private_key_pem: str | None = None) -> str:
    settings = get_settings()
    pem = (private_key_pem or settings.jwt_private_key.get_secret_value()).encode()
    private_key = load_pem_private_key(pem, password=None)
    now = int(time.time())
    payload = {
        "sub": str(device_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + settings.jwt_ttl_days * 86400,
    }
    return pyjwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str, *, public_key_pem: str | None = None) -> dict:
    settings = get_settings()
    pem = (public_key_pem or settings.jwt_public_key).encode()
    public_key = load_pem_public_key(pem)
    return pyjwt.decode(
        token,
        public_key,
        algorithms=[settings.jwt_algorithm],
        leeway=settings.jwt_leeway_seconds,
    )
