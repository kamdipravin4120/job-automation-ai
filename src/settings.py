"""Process-wide settings. Loaded once at boot; fails fast on missing required fields."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when required settings are missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Required secrets
    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    database_url: str
    celery_broker_url: str
    celery_result_backend: str

    # Optional
    gemini_api_key: SecretStr | None = None
    notion_api_key: SecretStr | None = None
    sentry_dsn: str | None = None

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "kv"] = "json"

    # Config file path (still YAML for feature config; secrets via env only)
    config_path: str = "config.yaml"
    profile_path: str = "data/profile.json"

    @classmethod
    def load(cls) -> "Settings":
        try:
            return cls()
        except ValidationError as e:
            missing = [
                ".".join(str(p) for p in err["loc"])
                for err in e.errors()
                if err["type"] == "missing"
            ]
            raise SettingsError(
                "Missing required settings: " + ", ".join(missing)
            ) from e


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
