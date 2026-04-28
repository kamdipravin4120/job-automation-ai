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
async def test_config_get_returns_yaml(async_client, redis_client, tmp_path):
    token = await _get_token(async_client, redis_client)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("scraping:\n  enabled: true\n")

    from src.settings import get_settings
    original_path = get_settings().config_path
    get_settings().config_path = str(cfg_file)
    try:
        r = await async_client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "scraping" in r.json()["yaml_text"]
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_config_put_valid_yaml(async_client, redis_client, tmp_path):
    token = await _get_token(async_client, redis_client)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("scraping:\n  enabled: true\n")

    from src.settings import get_settings
    original_path = get_settings().config_path
    get_settings().config_path = str(cfg_file)
    try:
        new_yaml = "scraping:\n  enabled: false\n  max_jobs: 50\n"
        r = await async_client.put(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            content=json.dumps({"yaml_text": new_yaml}),
        )
        assert r.status_code == 200
        assert "max_jobs" in r.json()["yaml_text"]
        assert cfg_file.read_text() == new_yaml
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_config_put_invalid_yaml_returns_400(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.put(
        "/api/v1/config",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        content=json.dumps({"yaml_text": "key: [unclosed bracket"}),
    )
    assert r.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_config_requires_auth(async_client):
    r = await async_client.get("/api/v1/config")
    assert r.status_code == 401
