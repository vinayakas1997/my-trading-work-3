from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class CacheEntry:
    data: dict[str, pd.DataFrame]
    timestamp: float = 0.0
    hits: int = 0


class PanelCache:
    """In-memory cache for OHLCV panel data with TTL and LRU eviction.

    Keys are generated from (symbols, from_ts, to_ts, interval) to ensure
    cache hits only when the exact same data slice is requested.
    """

    def __init__(self, max_size: int = 50, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()

    def _make_key(
        self,
        symbols: tuple[str, ...] | list[str] | str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str = "1d",
    ) -> str:
        if isinstance(symbols, str):
            symbols = (symbols,)
        sym_part = ",".join(sorted(symbols))
        return f"{sym_part}|{from_ts or ''}|{to_ts or ''}|{interval}"

    def get(
        self,
        symbols: tuple[str, ...] | list[str] | str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame] | None:
        key = self._make_key(symbols, from_ts, to_ts, interval)
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._default_ttl > 0 and (time.time() - entry.timestamp) > self._default_ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        entry.hits += 1
        return entry.data

    def set(
        self,
        data: dict[str, pd.DataFrame],
        symbols: tuple[str, ...] | list[str] | str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str = "1d",
    ) -> None:
        key = self._make_key(symbols, from_ts, to_ts, interval)
        if len(self._store) >= self._max_size and key not in self._store:
            self._store.popitem(last=False)
        self._store[key] = CacheEntry(data=data, timestamp=time.time())
        self._store.move_to_end(key)

    def invalidate(
        self,
        symbols: tuple[str, ...] | list[str] | str | None = None,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str | None = None,
    ) -> int:
        if symbols is None:
            count = len(self._store)
            self._store.clear()
            return count
        key_prefix = self._make_key(symbols, from_ts or 0, to_ts or 0, interval or "")
        keys_to_del = [k for k in self._store if k.startswith(key_prefix.split("|")[0])]
        for k in keys_to_del:
            del self._store[k]
        return len(keys_to_del)

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, Any]:
        if not self._store:
            return {"size": 0, "hits": 0, "misses": 0}
        total_hits = sum(e.hits for e in self._store.values())
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "ttl_seconds": self._default_ttl,
            "total_hits": total_hits,
        }


# Global singleton
_GLOBAL_CACHE: PanelCache | None = None


def get_cache() -> PanelCache:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = PanelCache()
    return _GLOBAL_CACHE


def reset_cache() -> None:
    global _GLOBAL_CACHE
    _GLOBAL_CACHE = None
