import json
import secrets
import uuid

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_list_empty(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/dlq",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_dismiss_run(async_client, redis_client, db_session):
    from src.data.models.run import Run
    token = await _get_token(async_client, redis_client)

    run = Run(
        kind="scrape",
        correlation_id=f"test-dlq-{uuid.uuid4()}",
        status="failed",
        error_code="scrape_failed",
        error_details={"msg": "timeout"},
    )
    db_session.add(run)
    await db_session.commit()

    r = await async_client.post(
        f"/api/v1/dlq/{run.id}/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["dismissed"] is True

    await db_session.refresh(run)
    assert run.status == "dismissed"


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_dismiss_nonexistent_returns_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        f"/api/v1/dlq/{uuid.uuid4()}/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_dlq_requires_auth(async_client):
    r = await async_client.get("/api/v1/dlq")
    assert r.status_code == 401
