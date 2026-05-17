import json
import logging
from io import StringIO

import structlog

from src.observability.logging import configure_logging, get_logger


def test_json_output_carries_correlation_id(monkeypatch, capsys):
    configure_logging(level="INFO", format="json")
    log = get_logger("test").bind(correlation_id="abc-123", run_id="r-1")
    log.info("hello", stage="scrape")
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(captured)
    assert payload["event"] == "hello"
    assert payload["correlation_id"] == "abc-123"
    assert payload["run_id"] == "r-1"
    assert payload["stage"] == "scrape"
    assert payload["level"] == "info"


def test_kv_output_is_human_readable(capsys):
    configure_logging(level="INFO", format="kv")
    log = get_logger("test")
    log.info("hello", stage="scrape")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "event='hello'" in line or "hello" in line
    assert "stage='scrape'" in line or "stage=scrape" in line
