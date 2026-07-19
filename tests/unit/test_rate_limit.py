"""Unit tests for the in-process rate limiter."""

from __future__ import annotations

import pytest
from app.errors import RateLimitError
from app.security.rate_limit import RateLimiter


def test_allows_up_to_limit() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("client-a")


def test_blocks_over_limit() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    limiter.check("b")
    limiter.check("b")
    with pytest.raises(RateLimitError) as exc:
        limiter.check("b")
    assert exc.value.retry_after > 0


def test_per_identity() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.check("c")
    limiter.check("d")
    with pytest.raises(RateLimitError):
        limiter.check("c")
