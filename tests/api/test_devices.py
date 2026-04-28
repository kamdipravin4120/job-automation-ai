import json
import secrets
import pytest


async def _pair_device(async_client, redis_client):
    """Helper: run full pairing flow and return token."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    device_priv = Ed25519PrivateKey.generate()
    device_pub_pem = device_priv.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    ).hex()

    secret = secrets.token_bytes(32).hex()
    await redis_client.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r = await async_client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    challenge_bytes = bytes.fromhex(r.json()["challenge"])
    sig = device_priv.sign(challenge_bytes).hex()
    r = await async_client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": device_pub_pem, "signature": sig,
    })
    return r.json()["token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_revoke_device_then_401(async_client, redis_client):
    import jwt as pyjwt
    token = await _pair_device(async_client, redis_client)
    payload = pyjwt.decode(token, options={"verify_signature": False})
    device_id = payload["sub"]

    # Revoke
    r = await async_client.delete(
        f"/api/v1/devices/{device_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    # Subsequent request must fail
    r = await async_client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
