import json
import secrets
import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    ).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_jobs_list_returns_paginated(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/jobs", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_jobs_detail_404(async_client, redis_client):
    import uuid
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
