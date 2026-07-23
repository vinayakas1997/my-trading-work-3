from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)

_INTERVAL_MAP: dict[str, str] = {
    "15min": "15m",
    "1W": "1wk",
    "1M": "1mo",
    "6M": "6mo",
}


class PriceClient:
    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")

    def _map_interval(self, interval: str) -> str:
        return _INTERVAL_MAP.get(interval, interval)

    def get_candles(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"adjusted": True}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        if interval is not None:
            params["interval"] = self._map_interval(interval)
        if limit is not None:
            params["limit"] = limit
        resp = request("GET", f"{self._base}/candles/{symbol.upper()}", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body
