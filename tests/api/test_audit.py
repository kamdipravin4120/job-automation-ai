import json
import secrets

import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_list_paginated(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_filter_by_action(async_client, redis_client, db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    token = await _get_token(async_client, redis_client)

    repo = AuditLogRepository(db_session)
    await repo.append(actor="test-device", action="unique.action.xyz", target="target")
    await db_session.commit()

    r = await async_client.get(
        "/api/v1/audit?action=unique.action.xyz",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert all(item["action"] == "unique.action.xyz" for item in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_requires_auth(async_client):
    r = await async_client.get("/api/v1/audit")
    assert r.status_code == 401
