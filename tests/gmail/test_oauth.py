import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from src.gmail.oauth import GmailOAuth, DeviceCodeResponse


def _oauth(tmp_path) -> GmailOAuth:
    return GmailOAuth(
        client_id="cid",
        client_secret="csec",
        token_path=str(tmp_path / ".gmail_token.json"),
    )


def test_init_device_flow_returns_code_response(tmp_path):
    oauth = _oauth(tmp_path)
    fake_resp = {
        "device_code": "dc123",
        "user_code": "ABCD-1234",
        "verification_url": "https://google.com/device",
        "interval": 5,
        "expires_in": 1800,
    }
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = fake_resp
        mock_post.return_value.raise_for_status = MagicMock()
        result = oauth.init_device_flow()
    assert result.user_code == "ABCD-1234"
    assert result.device_code == "dc123"
    assert result.verification_url == "https://google.com/device"


def test_poll_returns_pending_on_authorization_pending(tmp_path):
    oauth = _oauth(tmp_path)
    oauth._device_code = "dc123"
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"error": "authorization_pending"}
        mock_post.return_value.raise_for_status = MagicMock()
        status = oauth.poll_for_token()
    assert status == "pending"


def test_poll_saves_token_and_returns_authorized(tmp_path):
    oauth = _oauth(tmp_path)
    oauth._device_code = "dc123"
    fake_token = {"access_token": "at", "refresh_token": "rt", "token_type": "Bearer"}
    with patch("src.gmail.oauth.requests.post") as mock_post:
        mock_post.return_value.json.return_value = fake_token
        mock_post.return_value.raise_for_status = MagicMock()
        status = oauth.poll_for_token()
    assert status == "authorized"
    saved = json.loads(Path(oauth.token_path).read_text())
    assert saved["refresh_token"] == "rt"


def test_is_authorized_true_when_token_exists(tmp_path):
    oauth = _oauth(tmp_path)
    Path(oauth.token_path).write_text(json.dumps({"refresh_token": "rt", "access_token": "at"}))
    assert oauth.is_authorized() is True


def test_is_authorized_false_when_no_token(tmp_path):
    oauth = _oauth(tmp_path)
    assert oauth.is_authorized() is False
