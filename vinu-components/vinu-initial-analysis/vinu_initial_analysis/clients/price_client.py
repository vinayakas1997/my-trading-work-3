from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)


class PriceClient:
    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")

    def get_candles(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        if interval is not None:
            params["interval"] = interval
        if limit is not None:
            params["limit"] = limit
        resp = request("GET", f"{self._base}/candles/{symbol.upper()}", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body
