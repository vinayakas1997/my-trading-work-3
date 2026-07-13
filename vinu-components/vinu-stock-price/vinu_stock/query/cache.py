"""In-memory LRU cache for computed indicators."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

_MAX_CACHE_SIZE = 128
_CACHE_TTL_SEC = 300  # 5 minutes


def _make_cache_key(
    symbol: str,
    interval: str,
    from_ts: int | None,
    to_ts: int | None,
    indicators: frozenset[str],
    adjusted: bool,
) -> str:
    return f"{symbol}|{interval}|{from_ts}|{to_ts}|{','.join(sorted(indicators))}|{adjusted}"


class IndicatorCache:
    """Thread-safe LRU cache for indicator results."""

    def __init__(self, maxsize: int = _MAX_CACHE_SIZE, ttl: int = _CACHE_TTL_SEC) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()

    def get(
        self,
        symbol: str,
        interval: str,
        from_ts: int | None,
        to_ts: int | None,
        indicators: frozenset[str],
        adjusted: bool,
    ) -> list[dict[str, Any]] | None:
        key = _make_cache_key(symbol, interval, from_ts, to_ts, indicators, adjusted)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return data

    def set(
        self,
        symbol: str,
        interval: str,
        from_ts: int | None,
        to_ts: int | None,
        indicators: frozenset[str],
        adjusted: bool,
        data: list[dict[str, Any]],
    ) -> None:
        key = _make_cache_key(symbol, interval, from_ts, to_ts, indicators, adjusted)
        while len(self._cache) >= self._maxsize:
            self._cache.popitem(last=False)
        self._cache[key] = (time.monotonic(), data)

    def invalidate(self, symbol: str | None = None) -> None:
        if symbol is None:
            self._cache.clear()
        else:
            prefix = f"{symbol}|"
            keys_to_del = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]


_cache = IndicatorCache()


def get_cache() -> IndicatorCache:
    return _cache