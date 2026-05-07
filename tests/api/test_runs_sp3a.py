import json
import secrets
import uuid
import pytest
from src.data.models.run import Run
from src.data.repositories.runs import RunsRepository


@pytest.mark.asyncio(loop_scope="session")
async def test_set_jobs_found(db_session):
    run = Run(kind="scrape", correlation_id=str(uuid.uuid4()), status="succeeded")
    db_session.add(run)
    await db_session.flush()
    repo = RunsRepository(db_session)
    await repo.set_jobs_found(run.id, 42)
    await db_session.refresh(run)
    assert run.jobs_found == 42


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
async def test_run_out_has_jobs_found(async_client, redis_client, db_session):
    # Seed a run and commit so the API's own session can see it.
    run = Run(kind="scrape", correlation_id=str(uuid.uuid4()), status="succeeded")
    db_session.add(run)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get("/api/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert len(data["items"]) >= 1, "Expected at least one run in the list"
    first = data["items"][0]
    assert isinstance(first["jobs_found"], int)
    assert isinstance(first["steps"], list)
    assert first.get("error_details") is None or isinstance(first["error_details"], dict)
