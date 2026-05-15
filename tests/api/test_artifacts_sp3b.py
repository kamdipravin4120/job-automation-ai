import json
import secrets
import uuid
import pytest
from datetime import UTC, datetime


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
async def test_get_artifacts_unknown_job_returns_404(async_client, redis_client):
    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{uuid.uuid4()}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_get_artifacts_empty(async_client, redis_client, db_session):
    from src.data.models.job import Job
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Eng", company="Corp",
              jd_text="desc", url=None)
    db_session.add(job)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{job.id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cover_letter"] is None
    assert data["resume_text"] is None
    assert data["generated_at"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_artifacts_returns_latest(async_client, redis_client, db_session):
    from src.data.models.job import Job, JobArtifact
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Dev", company="Co",
              jd_text="jd", url=None)
    db_session.add(job)
    await db_session.flush()
    db_session.add(JobArtifact(job_id=job.id, kind="cover_letter", text="v1 cover", file_path="", version=1))
    db_session.add(JobArtifact(job_id=job.id, kind="cover_letter", text="v2 cover", file_path="", version=2))
    db_session.add(JobArtifact(job_id=job.id, kind="resume_text", text="resume body", file_path="", version=1))
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        f"/api/v1/jobs/{job.id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cover_letter"] == "v2 cover"
    assert data["resume_text"] == "resume body"
    assert data["generated_at"] is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_tailor_queues_task(async_client, redis_client, db_session):
    from unittest.mock import patch
    from src.data.models.job import Job
    job = Job(source="test", source_id=str(uuid.uuid4()), title="Eng", company="Co",
              jd_text="jd", url=None)
    db_session.add(job)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    with patch("src.api.routers.jobs.run_tailor") as mock_task:
        mock_task.delay.return_value = None
        r = await async_client.post(
            f"/api/v1/jobs/{job.id}/tailor",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["queued"] is True
    mock_task.delay.assert_called_once()
