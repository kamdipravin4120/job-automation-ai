import json
import secrets

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_challenge_returns_hex(async_client, redis_client):
    # Plant a bootstrap secret
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))

    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    assert r.status_code == 200
    data = r.json()
    assert "challenge" in data
    assert len(data["challenge"]) == 64  # 32 bytes hex


@pytest.mark.asyncio(loop_scope="session")
async def test_challenge_invalid_secret_returns_error(async_client):
    # Use a valid-format (64-char hex) secret that doesn't exist in Redis
    # Note: must be 64 hex chars due to field_validator on ChallengeRequest
    nonexistent_secret = secrets.token_bytes(32).hex()
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": nonexistent_secret})
    assert r.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_full_pairing_flow(async_client, redis_client, test_private_pem, test_public_pem):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat, load_pem_private_key,
    )

    # Generate device keypair
    device_priv_key = Ed25519PrivateKey.generate()
    device_priv_pem = device_priv_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode()
    device_pub_pem = device_priv_key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # Plant bootstrap secret
    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))

    # Step 1: get challenge
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    assert r.status_code == 200
    challenge_hex = r.json()["challenge"]
    challenge_bytes = bytes.fromhex(challenge_hex)

    # Step 2: sign challenge + pair
    signature = device_priv_key.sign(challenge_bytes).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret,
        "public_key": device_pub_pem,
        "signature": signature,
    })
    assert r.status_code == 201
    assert "token" in r.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_pair_invalid_signature_401(async_client, redis_client):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )

    device_priv_key = Ed25519PrivateKey.generate()
    device_pub_pem = device_priv_key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode()

    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))

    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    challenge_hex = r.json()["challenge"]

    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret,
        "public_key": device_pub_pem,
        "signature": "deadbeef" * 8,  # invalid — 32 chars, not a valid Ed25519 sig
    })
    assert r.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_protected_route_rejects_no_token(async_client):
    # GET /api/v1/jobs requires auth — 401 without token
    r = await async_client.get("/api/v1/jobs")
    assert r.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_protected_route_rejects_expired_token(async_client, test_private_pem):
    import time
    import jwt as pyjwt
    import uuid
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(test_private_pem.encode(), password=None)
    # Issue token that expired 1 hour ago
    now = int(time.time()) - 7200
    payload = {"sub": str(uuid.uuid4()), "jti": str(uuid.uuid4()), "iat": now, "exp": now + 3600}
    token = pyjwt.encode(payload, private_key, algorithm="EdDSA")

    r = await async_client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
