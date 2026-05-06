"""Process-wide settings. Loaded once at boot; fails fast on missing required fields."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, model_validator
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

    # JWT / Auth
    jwt_private_key: SecretStr = SecretStr("placeholder")
    jwt_public_key: str = ""
    jwt_algorithm: Literal["EdDSA"] = "EdDSA"
    jwt_ttl_days: int = 7
    jwt_rotation_days: int = 6
    jwt_leeway_seconds: int = 60

    # Bootstrap
    bootstrap_secret_ttl_seconds: int = 600

    # Rate limits
    rate_limit_pair_per_min: int = 5
    rate_limit_auth_per_min: int = 60

    # LinkedIn safety / rate limits
    linkedin_apps_per_hour: int = 10
    linkedin_searches_per_hour: int = 20
    linkedin_health_check_every_n: int = 5
    linkedin_circuit_max_failures: int = 3
    linkedin_circuit_cooldown_seconds: int = 300
    linkedin_cooldown_between_apps_ms: int = 4000

    # Gmail OAuth (device-code flow)
    gmail_client_id: str | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_token_path: str = ".gmail_token.json"

    # App
    app_version: str = "0.2.0"
    environment: Literal["development", "staging", "production"] = "development"

    @model_validator(mode='after')
    def _require_jwt_keys_in_non_development(self) -> 'Settings':
        if self.environment != "development":
            if not self.jwt_private_key.get_secret_value() or \
               self.jwt_private_key.get_secret_value() == "placeholder":
                raise ValueError("JWT_PRIVATE_KEY must be set in non-development environments")
            if not self.jwt_public_key:
                raise ValueError("JWT_PUBLIC_KEY must be set in non-development environments")
        return self

    @classmethod
    def load(cls) -> "Settings":
        try:
            return cls()
        except ValidationError as e:
            errors = [
                ".".join(str(p) for p in err["loc"]) + ": " + err.get("msg", err["type"])
                for err in e.errors()
                if err["type"] in ("missing", "value_error")
            ]
            raise SettingsError(
                "Settings validation failed: " + "; ".join(errors)
            ) from e


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
