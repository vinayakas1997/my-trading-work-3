"""Token bucket rate limiter for external API calls."""

from __future__ import annotations

import asyncio
import threading
import time


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Usage:
        limiter = TokenBucket(rate=10, per=60)  # 10 requests per 60 seconds
        limiter.wait()  # Blocks until a token is available
        make_api_call()
    """

    def __init__(self, rate: float, per: float = 60.0, burst: int | None = None) -> None:
        self._rate = rate
        self._per = per
        self._burst = burst or int(rate)
        self._tokens = float(self._burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(float(self._burst), self._tokens + elapsed * self._rate / self._per)
        self._last_refill = now

    def acquire(self, tokens: float = 1.0) -> bool:
        """Try to acquire tokens without blocking. Returns True if acquired."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait(self, tokens: float = 1.0) -> None:
        """Block until tokens are available (sync, blocks thread)."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
            sleep_time = (tokens - self._tokens) * self._per / self._rate
            time.sleep(max(0.01, min(sleep_time, 1.0)))

    async def wait_async(self, tokens: float = 1.0) -> None:
        """Non-blocking wait using asyncio.sleep."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
            sleep_time = (tokens - self._tokens) * self._per / self._rate
            await asyncio.sleep(max(0.01, min(sleep_time, 1.0)))
