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
async def test_searches_list_empty(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get("/api/v1/searches", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_create_and_list(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await async_client.post(
        "/api/v1/searches",
        headers=headers,
        json={"keywords": "Senior Python Engineer", "location": "Remote", "sources": ["linkedin"]},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["keywords"] == "Senior Python Engineer"
    assert data["location"] == "Remote"
    assert data["sources"] == ["linkedin"]
    assert data["enabled"] is True
    assert data["min_match_score"] == pytest.approx(0.6)
    search_id = data["id"]

    r = await async_client.get("/api/v1/searches", headers=headers)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert search_id in ids


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_patch(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await async_client.post(
        "/api/v1/searches",
        headers=headers,
        json={"keywords": "ML Engineer", "location": "USA"},
    )
    assert r.status_code == 201
    search_id = r.json()["id"]

    r = await async_client.patch(
        f"/api/v1/searches/{search_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_delete(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await async_client.post(
        "/api/v1/searches",
        headers=headers,
        json={"keywords": "To Delete", "location": "Anywhere"},
    )
    assert r.status_code == 201
    search_id = r.json()["id"]

    r = await async_client.delete(f"/api/v1/searches/{search_id}", headers=headers)
    assert r.status_code == 204

    r = await async_client.get("/api/v1/searches", headers=headers)
    ids = [s["id"] for s in r.json()]
    assert search_id not in ids


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_not_found(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.patch(
        f"/api/v1/searches/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},
    )
    assert r.status_code == 404
