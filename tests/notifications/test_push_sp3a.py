from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.notifications.push import PushEvent, PushService


def test_send_fcm_all_uses_provided_tokens():
    """send_fcm_all must use the tokens argument, not self._fcm_tokens."""
    svc = PushService(fcm_project_id="proj", fcm_service_account_json="{}")
    # Do NOT call svc.register_fcm_token — simulates real-world state (empty in-memory list)
    with patch.object(svc, "_send_fcm_one") as mock_send:
        svc.send_fcm_all(PushEvent(title="T", body="B"), tokens=["tok1", "tok2"])
    assert mock_send.call_count == 2


def test_send_event_passes_tokens_through():
    """send_event must forward the tokens kwarg to send_fcm_all."""
    svc = PushService(fcm_project_id="proj", fcm_service_account_json="{}")
    with patch.object(svc, "send_ntfy"), patch.object(svc, "send_fcm_all") as mock_fcm:
        svc.send_event(PushEvent(title="T", body="B"), tokens=["tokA"])
    mock_fcm.assert_called_once_with(PushEvent(title="T", body="B"), tokens=["tokA"])
