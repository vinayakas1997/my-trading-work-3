from __future__ import annotations

from typing import Any

from cachetools import TTLCache


class CorrelationCache:
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        self._impact_cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._correlation_cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._drawdown_cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    def _make_key(self, symbol: str, from_ts: int | None, to_ts: int | None) -> tuple:
        return (symbol.upper(), from_ts, to_ts)

    def get_impact(self, symbol: str, from_ts: int | None, to_ts: int | None) -> dict | None:
        return self._impact_cache.get(self._make_key(symbol, from_ts, to_ts))

    def set_impact(self, symbol: str, from_ts: int | None, to_ts: int | None, result: dict):
        self._impact_cache[self._make_key(symbol, from_ts, to_ts)] = result

    def get_correlation(self, symbol: str, from_ts: int | None, to_ts: int | None) -> dict | None:
        return self._correlation_cache.get(self._make_key(symbol, from_ts, to_ts))

    def set_correlation(self, symbol: str, from_ts: int | None, to_ts: int | None, result: dict):
        self._correlation_cache[self._make_key(symbol, from_ts, to_ts)] = result

    def get_drawdown(self, symbol: str, from_ts: int | None, to_ts: int | None) -> dict | None:
        return self._drawdown_cache.get(self._make_key(symbol, from_ts, to_ts))

    def set_drawdown(self, symbol: str, from_ts: int | None, to_ts: int | None, result: dict):
        self._drawdown_cache[self._make_key(symbol, from_ts, to_ts)] = result

    def invalidate(self, symbol: str | None = None):
        if symbol is None:
            self._impact_cache.clear()
            self._correlation_cache.clear()
            self._drawdown_cache.clear()
        else:
            key_prefix = (symbol.upper(),)
            for cache in (self._impact_cache, self._correlation_cache, self._drawdown_cache):
                keys_to_del = [k for k in cache if k[0] == key_prefix[0]]
                for k in keys_to_del:
                    del cache[k]
