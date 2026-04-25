import os
import pytest


def test_jwt_settings_parse():
    from src.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_algorithm == "EdDSA"
    assert s.jwt_ttl_days == 7
    assert s.jwt_rotation_days == 6
    assert s.jwt_leeway_seconds == 60
    assert s.bootstrap_secret_ttl_seconds == 600
    assert s.environment == "development"
    assert s.app_version == "0.2.0"
