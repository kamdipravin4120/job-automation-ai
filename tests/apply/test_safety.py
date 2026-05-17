import time
import pytest
from src.apply.safety import RateGuard, SessionMonitor, CircuitBreaker


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


def test_session_monitor_triggers_on_nth_check():
    mon = SessionMonitor(check_every_n=3)
    assert mon.should_check_health() is False  # 1
    assert mon.should_check_health() is False  # 2
    assert mon.should_check_health() is True   # 3 — triggers
    assert mon.should_check_health() is False  # 4
    assert mon.should_check_health() is False  # 5
    assert mon.should_check_health() is True   # 6 — triggers again


def test_session_monitor_reset_restarts_counter():
    mon = SessionMonitor(check_every_n=2)
    mon.should_check_health()  # 1
    mon.reset()
    assert mon.should_check_health() is False  # 1 again after reset
    assert mon.should_check_health() is True   # 2 triggers


def test_circuit_breaker_opens_after_max_failures():
    cb = CircuitBreaker(max_consecutive_failures=3, cooldown_seconds=60)
    assert cb.is_open() is False
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is False
    cb.record_failure()  # 3rd — trips
    assert cb.is_open() is True


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(max_consecutive_failures=2, cooldown_seconds=60)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is True
    cb.record_success()
    assert cb._consecutive_failures == 0


def test_circuit_breaker_closes_after_cooldown():
    cb = CircuitBreaker(max_consecutive_failures=1, cooldown_seconds=10)
    cb.record_failure()
    assert cb.is_open() is True
    cb._tripped_at -= 11.0
    assert cb.is_open() is False


def test_circuit_breaker_seconds_until_reset():
    cb = CircuitBreaker(max_consecutive_failures=1, cooldown_seconds=60)
    cb.record_failure()
    secs = cb.seconds_until_reset()
    assert 58 <= secs <= 61
