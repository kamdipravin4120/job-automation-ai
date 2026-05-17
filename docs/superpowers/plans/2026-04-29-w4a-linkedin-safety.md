# W4a: LinkedIn Safety Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable rate-limiting, periodic session health checks, and a circuit breaker to the LinkedIn apply/scrape flow so the bot self-throttles instead of triggering account bans.

**Architecture:** A new `src/apply/safety.py` module provides three independent components — `RateGuard` (token-bucket rate limiter), `SessionMonitor` (checks login health every N applications), `CircuitBreaker` (pauses batch after consecutive failures). `LinkedInEasyApplyBot.apply()` instantiates all three from settings and consults them on every iteration. Settings gains six new LinkedIn-specific threshold fields. The tasks/apply.py method-name mismatch (`apply_by_job_id` → `apply`) is fixed in the same PR.

**Tech Stack:** Python stdlib only (`time`, `threading`, `dataclasses`); no new dependencies. Tests use `pytest` + `freezegun` (already in requirements).

---

## File Map

**New files:**
- `src/apply/safety.py` — `RateGuard`, `SessionMonitor`, `CircuitBreaker`
- `tests/apply/__init__.py` — empty package marker
- `tests/apply/test_safety.py` — unit tests for all three components

**Modified files:**
- `src/settings.py` — add six LinkedIn safety threshold fields
- `src/apply/linkedin_easy_apply.py` — use safety components in `apply()` loop
- `src/tasks/apply.py` — fix `apply_by_job_id` → call `apply()` correctly

---

## Task 0: Settings fields for LinkedIn safety thresholds

**Files:**
- Modify: `src/settings.py:55-63` (after `rate_limit_auth_per_min`)
- Test: `tests/test_settings.py` (existing file — check if it exists, else create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings.py  (create if missing; add these tests if file exists)
import os, pytest
from unittest.mock import patch


def test_linkedin_safety_defaults():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
        "DATABASE_URL": "postgresql+asyncpg://x/x",
        "CELERY_BROKER_URL": "redis://x", "CELERY_RESULT_BACKEND": "redis://x",
    }):
        from src.settings import Settings
        s = Settings()
        assert s.linkedin_apps_per_hour == 10
        assert s.linkedin_searches_per_hour == 20
        assert s.linkedin_health_check_every_n == 5
        assert s.linkedin_circuit_max_failures == 3
        assert s.linkedin_circuit_cooldown_seconds == 300
        assert s.linkedin_cooldown_between_apps_ms == 4000
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_settings.py::test_linkedin_safety_defaults -v
```
Expected: `AttributeError: 'Settings' object has no attribute 'linkedin_apps_per_hour'`

- [ ] **Step 3: Add fields to `src/settings.py`**

Insert after line `rate_limit_auth_per_min: int = 60` (around line 56):

```python
    # LinkedIn safety / rate limits
    linkedin_apps_per_hour: int = 10
    linkedin_searches_per_hour: int = 20
    linkedin_health_check_every_n: int = 5
    linkedin_circuit_max_failures: int = 3
    linkedin_circuit_cooldown_seconds: int = 300
    linkedin_cooldown_between_apps_ms: int = 4000
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_settings.py::test_linkedin_safety_defaults -v
```
Expected: PASS

- [ ] **Step 5: Run full API suite to confirm no regression**

```bash
python -m pytest tests/api/ -q
```
Expected: `44 passed`

- [ ] **Step 6: Commit**

```bash
git add src/settings.py tests/test_settings.py
git commit -m "feat(safety): add LinkedIn safety threshold settings"
```

---

## Task 1: RateGuard — token-bucket rate limiter

**Files:**
- Create: `src/apply/safety.py`
- Create: `tests/apply/__init__.py`
- Create: `tests/apply/test_safety.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/apply/__init__.py  (empty)
```

```python
# tests/apply/test_safety.py
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
    # drain remaining 3599 — too slow to drain all, just drain via internal state
    guard._app_tokens = 0.0
    assert guard.consume_application() is False
    # advance time by 2 seconds via internal clock manipulation
    guard._last_refill -= 2.0
    assert guard.consume_application() is True  # refilled ~2 tokens
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/apply/test_safety.py -v
```
Expected: `ImportError: cannot import name 'RateGuard'`

- [ ] **Step 3: Create `src/apply/safety.py` with RateGuard**

```python
# src/apply/safety.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class RateGuard:
    """Token-bucket rate limiter for LinkedIn apply and search actions. Thread-safe."""

    apps_per_hour: int = 10
    searches_per_hour: int = 20

    _app_tokens: float = field(init=False)
    _search_tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: threading.Lock = field(init=False)

    def __post_init__(self) -> None:
        self._app_tokens = float(self.apps_per_hour)
        self._search_tokens = float(self.searches_per_hour)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._app_tokens = min(
            float(self.apps_per_hour),
            self._app_tokens + elapsed * (self.apps_per_hour / 3600.0),
        )
        self._search_tokens = min(
            float(self.searches_per_hour),
            self._search_tokens + elapsed * (self.searches_per_hour / 3600.0),
        )
        self._last_refill = now

    def consume_application(self) -> bool:
        """Returns True if a token was consumed, False if rate limit reached."""
        with self._lock:
            self._refill()
            if self._app_tokens < 1:
                return False
            self._app_tokens -= 1
            return True

    def consume_search(self) -> bool:
        """Returns True if a token was consumed, False if rate limit reached."""
        with self._lock:
            self._refill()
            if self._search_tokens < 1:
                return False
            self._search_tokens -= 1
            return True
```

- [ ] **Step 4: Run to verify tests pass**

```bash
python -m pytest tests/apply/test_safety.py -v -k "RateGuard"
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/apply/safety.py tests/apply/__init__.py tests/apply/test_safety.py
git commit -m "feat(safety): RateGuard token-bucket rate limiter"
```

---

## Task 2: SessionMonitor — periodic login health check

**Files:**
- Modify: `src/apply/safety.py` (append)
- Modify: `tests/apply/test_safety.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/apply/test_safety.py`:

```python
from src.apply.safety import SessionMonitor


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
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/apply/test_safety.py -v -k "SessionMonitor"
```
Expected: `ImportError: cannot import name 'SessionMonitor'`

- [ ] **Step 3: Append SessionMonitor to `src/apply/safety.py`**

```python

@dataclass
class SessionMonitor:
    """Re-verify LinkedIn login every N applications to catch mid-batch session expiry."""

    check_every_n: int = 5
    _apply_count: int = field(init=False, default=0)

    def should_check_health(self) -> bool:
        """Increment counter; return True when health check is due."""
        self._apply_count += 1
        return self._apply_count % self.check_every_n == 0

    def reset(self) -> None:
        self._apply_count = 0
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/apply/test_safety.py -v -k "SessionMonitor"
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/apply/safety.py tests/apply/test_safety.py
git commit -m "feat(safety): SessionMonitor for periodic login health checks"
```

---

## Task 3: CircuitBreaker — pause batch after consecutive failures

**Files:**
- Modify: `src/apply/safety.py` (append)
- Modify: `tests/apply/test_safety.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/apply/test_safety.py`:

```python
from src.apply.safety import CircuitBreaker


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
    # success does NOT reset an already-tripped breaker during cooldown
    cb.record_success()
    # But consecutive_failures is cleared — next trip requires another 2 failures
    assert cb._consecutive_failures == 0


def test_circuit_breaker_closes_after_cooldown():
    cb = CircuitBreaker(max_consecutive_failures=1, cooldown_seconds=10)
    cb.record_failure()
    assert cb.is_open() is True
    # Simulate cooldown elapsed by backdating the trip timestamp
    cb._tripped_at -= 11.0
    assert cb.is_open() is False


def test_circuit_breaker_seconds_until_reset():
    cb = CircuitBreaker(max_consecutive_failures=1, cooldown_seconds=60)
    cb.record_failure()
    secs = cb.seconds_until_reset()
    assert 58 <= secs <= 61
```

- [ ] **Step 2: Run to verify failures**

```bash
python -m pytest tests/apply/test_safety.py -v -k "CircuitBreaker"
```
Expected: `ImportError: cannot import name 'CircuitBreaker'`

- [ ] **Step 3: Append CircuitBreaker to `src/apply/safety.py`**

```python

@dataclass
class CircuitBreaker:
    """Halt batch apply after too many consecutive failures. Auto-resets after cooldown."""

    max_consecutive_failures: int = 3
    cooldown_seconds: int = 300

    _consecutive_failures: int = field(init=False, default=0)
    _tripped_at: float | None = field(init=False, default=None)

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._tripped_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.max_consecutive_failures:
            self._tripped_at = time.monotonic()

    def is_open(self) -> bool:
        """Returns True if the circuit is tripped (batch should pause)."""
        if self._tripped_at is None:
            return False
        elapsed = time.monotonic() - self._tripped_at
        if elapsed >= self.cooldown_seconds:
            self._tripped_at = None
            self._consecutive_failures = 0
            return False
        return True

    def seconds_until_reset(self) -> float:
        if self._tripped_at is None:
            return 0.0
        remaining = self.cooldown_seconds - (time.monotonic() - self._tripped_at)
        return max(0.0, remaining)
```

- [ ] **Step 4: Run all safety tests**

```bash
python -m pytest tests/apply/test_safety.py -v
```
Expected: all PASS (counts grow as you add tasks — by end of Task 3 expect 8 PASS)

- [ ] **Step 5: Commit**

```bash
git add src/apply/safety.py tests/apply/test_safety.py
git commit -m "feat(safety): CircuitBreaker halts batch after consecutive failures"
```

---

## Task 4: Integrate safety layer into LinkedInEasyApplyBot.apply()

**Files:**
- Modify: `src/apply/linkedin_easy_apply.py:18-55` (apply() method)

No new test file — safety components are unit-tested independently; integration is validated by existing apply tests.

- [ ] **Step 1: Add imports at top of `src/apply/linkedin_easy_apply.py`**

After the existing imports (line 10), add:

```python
from src.apply.safety import CircuitBreaker, RateGuard, SessionMonitor
from src.settings import get_settings
```

- [ ] **Step 2: Rewrite the `apply()` method**

Replace the `apply()` method (lines 18–55) with:

```python
    def apply(self, records: list[ApplicationRecord], limit: int | None = None) -> list[ApplicationRecord]:
        if not records:
            return []

        settings = get_settings()
        guard = RateGuard(
            apps_per_hour=settings.linkedin_apps_per_hour,
            searches_per_hour=settings.linkedin_searches_per_hour,
        )
        monitor = SessionMonitor(check_every_n=settings.linkedin_health_check_every_n)
        breaker = CircuitBreaker(
            max_consecutive_failures=settings.linkedin_circuit_max_failures,
            cooldown_seconds=settings.linkedin_circuit_cooldown_seconds,
        )

        storage_state_path = resolve_path(self.config_dir, self.config.storage_state_path)
        results: list[ApplicationRecord] = []
        max_records = limit or self.config.max_applications_per_run

        with browser_session(
            headless=self.config.headless,
            timeout_ms=self.config.timeout_ms,
            storage_state_path=storage_state_path,
        ) as (context, page):
            prompt_for_login(
                page,
                landing_url="https://www.linkedin.com/feed/",
                login_check_selector=self.config.login_check_selector,
            )

            is_logged_in = False
            for selector in (self.config.login_check_selector or ["img.global-nav__me-photo"]):
                if page.locator(selector).first.is_visible():
                    is_logged_in = True
                    break

            if not is_logged_in:
                self.logger.warning("Session appears expired. Requesting manual re-authentication.")
                prompt_for_login(page, landing_url="https://www.linkedin.com/feed/", login_check_selector="img.global-nav__me-photo")

            for record in records[:max_records]:
                if breaker.is_open():
                    wait_secs = breaker.seconds_until_reset()
                    self.logger.warning(
                        "Circuit breaker open — pausing batch for %.0f seconds", wait_secs
                    )
                    time.sleep(min(wait_secs, 60))
                    if breaker.is_open():
                        record.status = "error"
                        record.notes = "Batch halted: circuit breaker still open after cooldown."
                        results.append(record)
                        continue

                if not guard.consume_application():
                    self.logger.warning("Application rate limit reached — stopping batch.")
                    record.status = "error"
                    record.notes = "Batch halted: LinkedIn application rate limit reached."
                    results.append(record)
                    break

                if monitor.should_check_health():
                    still_logged_in = any(
                        page.locator(sel).first.is_visible()
                        for sel in (self.config.login_check_selector or ["img.global-nav__me-photo"])
                    )
                    if not still_logged_in:
                        self.logger.warning("Session expired mid-batch. Re-authenticating.")
                        prompt_for_login(page, landing_url="https://www.linkedin.com/feed/", login_check_selector="img.global-nav__me-photo")

                app_page = context.new_page()
                app_page.set_default_timeout(self.config.timeout_ms)
                try:
                    updated = self._apply_single(app_page, record)
                    results.append(updated)
                    if updated.status == "applied":
                        breaker.record_success()
                    else:
                        breaker.record_failure()
                except Exception as exc:
                    record.status = "error"
                    record.notes = f"Application failed: {exc}"
                    results.append(record)
                    breaker.record_failure()
                    self.logger.exception("Easy Apply failed for %s", record.job_id)
                finally:
                    app_page.close()

                human_delay(app_page if not app_page.is_closed() else page,
                            settings.linkedin_cooldown_between_apps_ms,
                            settings.linkedin_cooldown_between_apps_ms + 2000)

        return results
```

- [ ] **Step 3: Add `import time` if not already present**

Check top of `src/apply/linkedin_easy_apply.py` — if `import time` is absent, add it after the stdlib imports.

- [ ] **Step 4: Run the existing apply tests (if any) and full API suite**

```bash
python -m pytest tests/apply/ tests/api/ -q
```
Expected: all pass. If `tests/apply/` has no apply-bot tests, `apply/` tests = 8 PASS (from Tasks 1-3).

- [ ] **Step 5: Commit**

```bash
git add src/apply/linkedin_easy_apply.py
git commit -m "feat(safety): integrate RateGuard/SessionMonitor/CircuitBreaker into apply loop"
```

---

## Task 5: Fix tasks/apply.py method mismatch

**Files:**
- Modify: `src/tasks/apply.py`

Currently calls `flow.apply_by_job_id(job_id=job_id)` but `LinkedInEasyApplyBot` only has `apply(records, limit)`. Fix: load the ApplicationRecord from DB by job_id and call `apply([record], limit=1)`.

- [ ] **Step 1: Rewrite `src/tasks/apply.py`**

```python
"""Apply stage wrapper — Celery task that runs LinkedInEasyApplyBot for a single job."""
from __future__ import annotations

from src.tasks.base import pipeline_task


@pipeline_task(stage="apply", max_retries=1, queue="browser")
def run_apply(*, correlation_id: str, job_id: str) -> dict:
    return _apply_to_job(correlation_id, job_id)


def _apply_to_job(correlation_id: str, job_id: str) -> dict:
    from pathlib import Path

    from src.apply.linkedin_easy_apply import LinkedInEasyApplyBot
    from src.models import ApplicationRecord
    from src.observability.logging import get_logger
    from src.utils.config import load_config

    log = get_logger("tasks.apply")
    config = load_config(Path("config.yaml"))
    flow = LinkedInEasyApplyBot(config, Path("."), log)

    # Build a minimal ApplicationRecord from job_id for the bot.
    # Full DB-backed lookup lands in W5 when the SQL layer is wired into tasks.
    record = ApplicationRecord(job_id=job_id, correlation_id=correlation_id)
    results = flow.apply([record], limit=1)
    submitted = any(r.status == "applied" for r in results)
    return {"submitted": submitted}
```

- [ ] **Step 2: Verify import works (no syntax errors)**

```bash
python -c "from src.tasks.apply import run_apply; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/api/ tests/apply/ -q
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/tasks/apply.py
git commit -m "fix(tasks): apply task calls apply([record]) not apply_by_job_id()"
```
