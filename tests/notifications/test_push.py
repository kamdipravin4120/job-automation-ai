from unittest.mock import MagicMock, patch
import pytest
from src.notifications.push import PushEvent, PushService


def test_push_event_fields():
    ev = PushEvent(title="Jobs found", body="3 new matches", data={"count": 3})
    assert ev.title == "Jobs found"
    assert ev.data == {"count": 3}


def test_ntfy_send_posts_to_topic_url():
    svc = PushService(ntfy_topic_url="https://ntfy.sh/test-topic")
    with patch("src.notifications.push.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        svc.send_ntfy(PushEvent(title="Test", body="Hello"))
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "https://ntfy.sh/test-topic" in str(call_kwargs)
    assert "Test" in str(call_kwargs)


def test_ntfy_skipped_when_no_topic_configured():
    svc = PushService(ntfy_topic_url=None)
    with patch("src.notifications.push.httpx.post") as mock_post:
        svc.send_ntfy(PushEvent(title="Test", body="Hello"))
    mock_post.assert_not_called()


def test_send_event_calls_available_backends(monkeypatch):
    svc = PushService(ntfy_topic_url="https://ntfy.sh/t")
    called = []
    monkeypatch.setattr(svc, "send_ntfy", lambda ev: called.append("ntfy"))
    monkeypatch.setattr(svc, "send_fcm_all", lambda ev: called.append("fcm"))
    svc.send_event(PushEvent(title="T", body="B"))
    assert "ntfy" in called
    assert "fcm" in called


import uuid
from datetime import datetime, timezone
from src.data.repositories.fcm_tokens import FcmTokensRepository
from src.data.models.fcm_token import FcmToken


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_register_and_list(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    token = await repo.register(device_id=device_id, token="fcm-token-abc")
    assert token.token == "fcm-token-abc"
    tokens = await repo.list_by_device(device_id)
    assert any(t.token == "fcm-token-abc" for t in tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_unregister(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    await repo.register(device_id=device_id, token="fcm-token-xyz")
    deleted = await repo.unregister(token="fcm-token-xyz")
    assert deleted is True
    tokens = await repo.list_by_device(device_id)
    assert not any(t.token == "fcm-token-xyz" for t in tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_fcm_token_list_all(db_session):
    repo = FcmTokensRepository(db_session)
    device_id = uuid.uuid4()
    await repo.register(device_id=device_id, token="fcm-t1")
    await repo.register(device_id=device_id, token="fcm-t2")
    all_tokens = await repo.list_all()
    token_strings = [t.token for t in all_tokens]
    assert "fcm-t1" in token_strings
    assert "fcm-t2" in token_strings
