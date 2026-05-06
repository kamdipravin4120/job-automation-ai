import json
import secrets
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


async def _get_token(async_client, redis_client) -> str:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_register_fcm_token(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-abc-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["registered"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_unregister_fcm_token(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-to-remove"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await async_client.delete(
        "/api/v1/notifications/fcm/fcm-to-remove",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_notifications_requires_auth(async_client):
    r = await async_client.post(
        "/api/v1/notifications/fcm/register",
        json={"fcm_token": "fcm-xyz"},
    )
    assert r.status_code == 401
