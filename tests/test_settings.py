import os
import pytest
from unittest.mock import patch

from src.settings import Settings, SettingsError


REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DATABASE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
]


def test_missing_required_env_fails_fast(monkeypatch):
    for var in REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(SettingsError) as excinfo:
        Settings.load()

    message = str(excinfo.value)
    # At least one required field name should appear in the error message
    assert any(
        var.lower() in message.lower() for var in REQUIRED_ENV_VARS
    ), f"expected a missing field name in error, got: {message}"


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "kv")

    settings = Settings.load()

    assert settings.openai_api_key.get_secret_value() == "x"
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "kv"


def test_linkedin_safety_defaults():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
        "DATABASE_URL": "postgresql+asyncpg://x/x",
        "CELERY_BROKER_URL": "redis://x", "CELERY_RESULT_BACKEND": "redis://x",
    }):
        from importlib import reload
        import src.settings as settings_mod
        reload(settings_mod)
        s = settings_mod.Settings()
        assert s.linkedin_apps_per_hour == 10
        assert s.linkedin_searches_per_hour == 20
        assert s.linkedin_health_check_every_n == 5
        assert s.linkedin_circuit_max_failures == 3
        assert s.linkedin_circuit_cooldown_seconds == 300
        assert s.linkedin_cooldown_between_apps_ms == 4000


def test_gmail_settings_defaults():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
        "DATABASE_URL": "postgresql+asyncpg://x/x",
        "CELERY_BROKER_URL": "redis://x", "CELERY_RESULT_BACKEND": "redis://x",
    }):
        from importlib import reload
        import src.settings as settings_mod
        reload(settings_mod)
        s = settings_mod.Settings()
        assert s.gmail_client_id is None
        assert s.gmail_client_secret is None
        assert s.gmail_token_path == ".gmail_token.json"
