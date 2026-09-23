from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)

_INTERVAL_MAP: dict[str, str] = {
    "15min": "15m",
    "1min": "1m",
    "5min": "5m",
    "1W": "1wk",
    "1M": "1mo",
    "6M": "6mo",
}
# "1H"/"4H"/"1D" are deliberately absent -- vinu-stock-price's own
# interval_to_seconds() lowercases and already accepts "1h"/"4h"/"1d"
# verbatim, so the identity fallback below (_map_interval's .get default)
# already worked for them. "5min" was NOT covered the same way (found
# 2026-09-23: vinu-stock-price expects "5m", never accepts "5min") --
# every one of the 28 angles declares "5min", so every angle's 5min
# fetch was silently failing (caught by _fetch_bars's blanket except,
# returning an empty DataFrame) and retrying forever on every scheduled
# cycle, since a df.empty result is never written or recorded in
# RunLog. See missing-pieces-of-system/angle-comprehension-hierarchy/.

# 1-minute bars are dense enough that a single request over a multi-year
# window silently truncates at the server's row limit (Bug-8: price_change_5m
# /15m were only populated for ~1% of news_price_causality events because
# no 1-minute pass existed at all; once added, an unpaginated fetch would
# have just moved the truncation from "5m/15m always empty" to "1m data
# missing after the first ~4-5 months"). Chunk minute-level fetches so a
# full multi-year window is actually returned.
_MINUTE_CHUNK_SECONDS = 45 * 86400


class PriceClient:
    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")

    def _map_interval(self, interval: str) -> str:
        return _INTERVAL_MAP.get(interval, interval)

    def get_watchlist(self) -> list[str]:
        resp = request("GET", f"{self._base}/stock/watchlist/tickers")
        resp.raise_for_status()
        body = resp.json()
        return body.get("tickers", []) if isinstance(body, dict) else body

    def get_candles(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str | None = None,
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        mapped = self._map_interval(interval) if interval is not None else None
        if mapped == "1m" and from_ts is not None and to_ts is not None and (to_ts - from_ts) > _MINUTE_CHUNK_SECONDS:
            out: list[dict[str, Any]] = []
            cursor = from_ts
            while cursor < to_ts:
                chunk_end = min(cursor + _MINUTE_CHUNK_SECONDS, to_ts)
                out.extend(self._get_candles_page(symbol, cursor, chunk_end, mapped, limit))
                cursor = chunk_end
            return out
        return self._get_candles_page(symbol, from_ts, to_ts, mapped, limit)

    def _get_candles_page(
        self,
        symbol: str,
        from_ts: int | None,
        to_ts: int | None,
        mapped_interval: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"adjusted": True}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        if mapped_interval is not None:
            params["interval"] = mapped_interval
        if limit is not None:
            params["limit"] = limit
        resp = request("GET", f"{self._base}/stock/candles/{symbol.upper()}", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body
