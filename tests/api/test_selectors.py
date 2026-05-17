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
async def test_selectors_list_pending(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/selectors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_approve(async_client, redis_client, db_session, tmp_path):
    from src.data.models.selector_override import SelectorOverride
    from src.settings import get_settings
    import yaml

    token = await _get_token(async_client, redis_client)

    row = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.job_card",
        selector=".new-job-card",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.commit()

    original_path = get_settings().config_path
    get_settings().config_path = str(tmp_path / "config.yaml")
    try:
        r = await async_client.post(
            f"/api/v1/selectors/{row.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        overrides_file = tmp_path / "config.overrides.yaml"
        assert overrides_file.exists()
        data = yaml.safe_load(overrides_file.read_text())
        assert data["scraping.linkedin.job_card"] == ".new-job-card"
    finally:
        get_settings().config_path = original_path


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_reject(async_client, redis_client, db_session):
    from src.data.models.selector_override import SelectorOverride
    token = await _get_token(async_client, redis_client)

    row = SelectorOverride(
        source="naukri",
        key_path="scraping.naukri.title",
        selector=".job-title-new",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.commit()

    r = await async_client.post(
        f"/api/v1/selectors/{row.id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_approve_nonexistent_returns_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.post(
        f"/api/v1/selectors/{uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_selectors_requires_auth(async_client):
    r = await async_client.get("/api/v1/selectors")
    assert r.status_code == 401
