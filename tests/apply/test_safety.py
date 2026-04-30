import pytest
from src.apply.safety import RateGuard, SessionMonitor


def test_rate_guard_allows_within_limit():
    guard = RateGuard(apps_per_hour=2, searches_per_hour=10)
    assert guard.consume_application() is True
    assert guard.consume_application() is True


def test_rate_guard_blocks_over_limit():
    guard = RateGuard(apps_per_hour=1, searches_per_hour=10)
    assert guard.consume_application() is True
    assert guard.consume_application() is False


def test_rate_guard_search_independent_of_app():
    guard = RateGuard(apps_per_hour=1, searches_per_hour=3)
    assert guard.consume_application() is True
    assert guard.consume_application() is False
    assert guard.consume_search() is True
    assert guard.consume_search() is True
    assert guard.consume_search() is True
    assert guard.consume_search() is False


def test_rate_guard_tokens_refill_over_time():
    guard = RateGuard(apps_per_hour=3600)  # 1 token/sec
    assert guard.consume_application() is True
    guard._app_tokens = 0.0
    assert guard.consume_application() is False
    guard._last_refill -= 2.0
    assert guard.consume_application() is True


def test_session_monitor_triggers_on_nth_check():
    mon = SessionMonitor(check_every_n=3)
    assert mon.should_check_health() is False  # 1
    assert mon.should_check_health() is False  # 2
    assert mon.should_check_health() is True   # 3
    assert mon.should_check_health() is False  # 4
    assert mon.should_check_health() is False  # 5
    assert mon.should_check_health() is True   # 6


def test_session_monitor_reset_restarts_counter():
    mon = SessionMonitor(check_every_n=2)
    mon.should_check_health()
    mon.reset()
    assert mon.should_check_health() is False
    assert mon.should_check_health() is True
