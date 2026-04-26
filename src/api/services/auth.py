from __future__ import annotations

import json
import secrets
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.security import create_jwt
from src.data.repositories.devices import DevicesRepository


async def store_challenge(redis: aioredis.Redis, bootstrap_secret: str) -> str:
    """Verify bootstrap secret exists, store challenge, return challenge hex. Empty string = invalid."""
    key = f"bootstrap:{bootstrap_secret}"
    if not await redis.exists(key):
        return ""
    challenge = secrets.token_bytes(32)
    await redis.setex(f"challenge:{bootstrap_secret}", 60, challenge.hex())
    return challenge.hex()


async def pair_device(
    *,
    redis: aioredis.Redis,
    db: AsyncSession,
    bootstrap_secret: str,
    public_key_pem: str,
    signature_hex: str,
    pairing_ip: str | None,
) -> str:
    """Verify bootstrap secret + proof-of-possession, create device, return JWT."""
    # Verify bootstrap secret still valid
    bs_key = f"bootstrap:{bootstrap_secret}"
    if not await redis.exists(bs_key):
        raise ValueError("invalid_bootstrap_secret")

    # Retrieve challenge
    ch_val = await redis.get(f"challenge:{bootstrap_secret}")
    if not ch_val:
        raise ValueError("challenge_expired")
    challenge_bytes = bytes.fromhex(ch_val)

    # Verify Ed25519 signature
    try:
        pub_key: Ed25519PublicKey = load_pem_public_key(public_key_pem.encode())  # type: ignore[assignment]
        pub_key.verify(bytes.fromhex(signature_hex), challenge_bytes)
    except (InvalidSignature, Exception):
        raise ValueError("invalid_signature")

    # Consume bootstrap secret (single-use)
    await redis.delete(bs_key)
    await redis.delete(f"challenge:{bootstrap_secret}")

    # Create device row
    repo = DevicesRepository(db)
    device = await repo.create(public_key=public_key_pem, pairing_ip=pairing_ip)
    await db.commit()

    return create_jwt(device.id)
