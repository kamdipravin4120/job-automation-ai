from unittest.mock import MagicMock, patch
import pytest


def test_push_on_complete_sends_event():
    mock_service = MagicMock()
    with patch("src.tasks.base._build_push_service", return_value=mock_service):
        from src.tasks.base import _push_on_complete
        _push_on_complete(stage="scrape", result={"jobs_found": 3})
    mock_service.send_event.assert_called_once()
    event = mock_service.send_event.call_args[0][0]
    assert "scrape" in event.title.lower() or "scrape" in event.body.lower()


def test_push_on_complete_never_raises():
    with patch("src.tasks.base._build_push_service", side_effect=Exception("no settings")):
        from src.tasks.base import _push_on_complete
        _push_on_complete(stage="apply", result={})  # must not raise
