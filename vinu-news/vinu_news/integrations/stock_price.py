"""HTTP client for vinu-stock-price API (TASK-N03)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from vinu_news.net import request as http_request

LOG = logging.getLogger(__name__)


class StockPriceClient:
    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def get_candles(
        self,
        symbol: str,
        *,
        from_ts: int | None = None,
        to_ts: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        url = f"{self._base}/candles/{symbol.strip().upper()}"
        params: dict[str, Any] = {"limit": limit}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        try:
            resp = http_request("GET", url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            body = resp.json()
            return list(body.get("data") or [])
        except requests.RequestException as exc:
            LOG.warning("Stock price API unavailable: %s", exc)
            return []
