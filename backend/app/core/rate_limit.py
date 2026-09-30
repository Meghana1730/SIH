"""A tiny in-memory rate limiter (sliding window).

Used to slow down password guessing and sign-up spam. Limitations (fine for the hackathon's
single API process): it forgets everything on restart and is not shared between processes.
A real deployment would keep these counters in a shared store such as Redis.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    """Allows at most `max_events` per key within the last `window_seconds`."""

    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        events = self._events.get(key)
        if events is None:
            return deque()
        while events and events[0] <= now - self.window_seconds:
            events.popleft()
        if not events:
            del self._events[key]
        return events

    def is_limited(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, self._clock())) >= self.max_events

    def retry_after_seconds(self, key: str) -> int:
        """Seconds until one more event is allowed for this key (0 if allowed now)."""
        with self._lock:
            now = self._clock()
            events = self._recent(key, now)
            if len(events) < self.max_events:
                return 0
            return max(1, math.ceil(events[0] + self.window_seconds - now))

    def hit(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._recent(key, now)
            self._events.setdefault(key, deque()).append(now)
            if len(self._events) > self._max_keys:
                self._drop_oldest_keys(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def _drop_oldest_keys(self, now: float) -> None:
        # Keep memory bounded: forget expired keys first, then the least recently used ones.
        for key in list(self._events):
            self._recent(key, now)
        if len(self._events) > self._max_keys:
            by_last_event = sorted(self._events, key=lambda k: self._events[k][-1])
            for key in by_last_event[: len(self._events) - self._max_keys]:
                del self._events[key]
