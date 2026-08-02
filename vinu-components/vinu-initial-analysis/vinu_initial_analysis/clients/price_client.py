from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)

_INTERVAL_MAP: dict[str, str] = {
    "15min": "15m",
    "1min": "1m",
    "1W": "1wk",
    "1M": "1mo",
    "6M": "6mo",
}

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
