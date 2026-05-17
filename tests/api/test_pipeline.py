import json
import secrets
import uuid

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    s = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{s}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": s})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={"bootstrap_secret": s, "public_key": pub, "signature": sig})
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_requires_idempotency_key(async_client, redis_client, celery_app_eager):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        "/api/v1/pipeline/trigger",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_idempotency_replay(async_client, redis_client, celery_app_eager):
    token = await _get_token(async_client, redis_client)
    key = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": key}

    r1 = await async_client.post("/api/v1/pipeline/trigger", headers=headers, json={})
    r2 = await async_client.post("/api/v1/pipeline/trigger", headers=headers, json={})

    # Idempotency is enforced by IdempotencyMiddleware (HTTP cache by key), not by the
    # endpoint itself. r2 returns the cached r1 response from Redis.
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["correlation_id"] == r2.json()["correlation_id"]
