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


@pytest.mark.asyncio(loop_scope="session")
async def test_application_out_has_briefing_json(async_client, redis_client, db_session):
    from src.data.models.application import Application
    briefing = [{"question": "Q1", "rationale": "R1", "star_points": ["S1", "S2"]}]
    app = Application(
        job_id=uuid.uuid4(),
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=json.dumps(briefing),
    )
    db_session.add(app)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    r = await async_client.get(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    target = next((i for i in items if i["id"] == str(app.id)), None)
    assert target is not None
    assert isinstance(target["briefing_json"], list)
    assert target["briefing_json"][0]["question"] == "Q1"
    assert target["briefing_json"][0]["star_points"] == ["S1", "S2"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_brief_stores_and_returns(async_client, redis_client, db_session):
    from unittest.mock import MagicMock, mock_open, patch
    from src.data.models.application import Application
    from src.data.models.job import Job

    job = Job(source="test", source_id=str(uuid.uuid4()), title="SWE", company="Acme",
              jd_text="Build systems", url=None)
    db_session.add(job)
    await db_session.flush()

    app = Application(
        job_id=job.id,
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=None,
    )
    db_session.add(app)
    await db_session.commit()

    mock_profile = {
        "name": "Test User", "email": "t@t.com", "phone": "555",
        "location": "Remote", "headline": "Eng", "summary": "Eng",
        "skills": [], "experience": [], "education": [], "projects": [], "certifications": [],
    }
    fake_briefing = [{"question": "Q?", "rationale": "Because", "star_points": ["S1", "S2"]}]
    mock_cfg = MagicMock()
    mock_cfg.resume = MagicMock()
    mock_cfg.app.profile_path = "data/profile.json"

    token = await _get_token(async_client, redis_client)
    with patch("src.utils.config.load_config", return_value=mock_cfg), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.open", mock_open(read_data=json.dumps(mock_profile))), \
         patch("src.resume.engine.ResumeService") as MockSvc:
        MockSvc.return_value.generate_interview_briefing.return_value = fake_briefing
        r = await async_client.post(
            f"/api/v1/applications/{app.id}/brief",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["briefing_json"], list)
    assert data["briefing_json"][0]["question"] == "Q?"
    assert data["briefing_json"][0]["star_points"] == ["S1", "S2"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_brief_idempotent(async_client, redis_client, db_session):
    from unittest.mock import patch
    from src.data.models.application import Application

    existing = [{"question": "Existing?", "rationale": "R", "star_points": ["S"]}]
    app = Application(
        job_id=uuid.uuid4(),
        submitted_at=datetime.now(UTC),
        channel="linkedin",
        current_status="applied",
        briefing_json=json.dumps(existing),
    )
    db_session.add(app)
    await db_session.commit()

    token = await _get_token(async_client, redis_client)
    with patch("src.resume.engine.ResumeService") as MockSvc:
        r = await async_client.post(
            f"/api/v1/applications/{app.id}/brief",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    assert r.json()["briefing_json"][0]["question"] == "Existing?"
    MockSvc.return_value.generate_interview_briefing.assert_not_called()
