from unittest.mock import MagicMock, patch
import pytest
from src.gmail.client import GmailClient, EmailMessage


def test_list_unread_returns_email_messages():
    client = GmailClient(credentials=MagicMock())
    fake_list = {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
    fake_msg1 = {
        "id": "msg1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Interview invite"},
                {"name": "From", "value": "hr@example.com"},
                {"name": "Date", "value": "Mon, 28 Apr 2026 10:00:00 +0000"},
            ],
            "body": {"data": "SGkgdGhlcmU="},
            "parts": [],
        },
    }
    fake_msg2 = {
        "id": "msg2",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Application received"},
                {"name": "From", "value": "no-reply@company.com"},
                {"name": "Date", "value": "Mon, 28 Apr 2026 09:00:00 +0000"},
            ],
            "body": {"data": "VGhhbmtzIQ=="},
            "parts": [],
        },
    }
    with patch("src.gmail.client.build") as mock_build:
        svc = MagicMock()
        mock_build.return_value = svc
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = fake_list
        svc.users.return_value.messages.return_value.get.return_value.execute.side_effect = [fake_msg1, fake_msg2]
        messages = client.list_unread(max_results=10)
    assert len(messages) == 2
    assert messages[0].subject == "Interview invite"
    assert messages[0].body == "Hi there"
    assert messages[1].subject == "Application received"


def test_list_unread_returns_empty_when_no_messages():
    client = GmailClient(credentials=MagicMock())
    with patch("src.gmail.client.build") as mock_build:
        svc = MagicMock()
        mock_build.return_value = svc
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {}
        messages = client.list_unread(max_results=10)
    assert messages == []
