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
        with self._lock:
            self._refill()
            if self._app_tokens < 1:
                return False
            self._app_tokens -= 1
            return True

    def consume_search(self) -> bool:
        with self._lock:
            self._refill()
            if self._search_tokens < 1:
                return False
            self._search_tokens -= 1
            return True


@dataclass
class SessionMonitor:
    """Re-verify LinkedIn login every N applications to catch mid-batch session expiry."""

    check_every_n: int = 5
    _apply_count: int = field(init=False, default=0)

    def should_check_health(self) -> bool:
        self._apply_count += 1
        return self._apply_count % self.check_every_n == 0

    def reset(self) -> None:
        self._apply_count = 0
