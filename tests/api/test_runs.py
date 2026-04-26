import json
import secrets
import uuid
import pytest


async def _get_token(async_client, redis_client) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    s = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{s}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": s})
    sig = priv.sign(bytes.fromhex(r.json()["challenge"])).hex()
    r = await async_client.post("/api/v1/auth/pair", json={"bootstrap_secret": s, "public_key": pub, "signature": sig})
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_runs_list(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get("/api/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "items" in r.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_run_detail_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(f"/api/v1/runs/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
