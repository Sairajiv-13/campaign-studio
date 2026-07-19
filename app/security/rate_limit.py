"""In-process fixed-window rate limiter.

This service is a single stateless process (generation is CPU/LLM-bound, not
horizontally sharded state), so an in-memory limiter is the right weight — no
Redis dependency. Behind multiple replicas each instance limits independently;
that is documented, and swapping in a shared store is a small change if needed.
"""

from __future__ import annotations

import threading
import time

from app.errors import RateLimitError


class RateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._lock = threading.Lock()
        # identity -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def check(self, identity: str) -> None:
        now = time.time()
        with self._lock:
            start, count = self._buckets.get(identity, (now, 0))
            if now - start >= self._window:
                start, count = now, 0
            count += 1
            self._buckets[identity] = (start, count)
            if count > self._limit:
                retry_after = max(1, int(self._window - (now - start)))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
