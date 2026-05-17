# tests/api/test_gmail.py
def test_application_model_has_email_status():
    from src.data.models.application import Application
    assert hasattr(Application, "email_status")


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
async def test_gmail_status_not_authorized(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/gmail/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["authorized"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_gmail_init_requires_client_id(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        "/api/v1/gmail/oauth/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503


@pytest.mark.asyncio(loop_scope="session")
async def test_gmail_requires_auth(async_client):
    r = await async_client.get("/api/v1/gmail/status")
    assert r.status_code == 401
