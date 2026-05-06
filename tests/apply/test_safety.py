import time
import pytest
from src.apply.safety import RateGuard


def test_rate_guard_allows_within_limit():
    guard = RateGuard(apps_per_hour=2, searches_per_hour=10)
    assert guard.consume_application() is True
    assert guard.consume_application() is True


def test_rate_guard_blocks_over_limit():
    guard = RateGuard(apps_per_hour=1, searches_per_hour=10)
    assert guard.consume_application() is True
    assert guard.consume_application() is False  # exhausted


def test_rate_guard_search_independent_of_app():
    guard = RateGuard(apps_per_hour=1, searches_per_hour=3)
    assert guard.consume_application() is True
    assert guard.consume_application() is False
    # searches unaffected
    assert guard.consume_search() is True
    assert guard.consume_search() is True
    assert guard.consume_search() is True
    assert guard.consume_search() is False


def test_rate_guard_tokens_refill_over_time():
    guard = RateGuard(apps_per_hour=3600)  # 1 token/sec
    assert guard.consume_application() is True
    guard._app_tokens = 0.0
    assert guard.consume_application() is False
    # advance time by 2 seconds via internal clock manipulation
    guard._last_refill -= 2.0
    assert guard.consume_application() is True  # refilled ~2 tokens
