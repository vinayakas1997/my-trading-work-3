"""HTTP client for vinu-stock-price candles API."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from vinu_features.config import load_config


class CandleClient(Protocol):
    def fetch_candles(
        self,
        symbol: str,
        *,
        interval: str,
        from_ts: int | None,
        to_ts: int | None,
        limit: int = 50000,
    ) -> list[dict[str, Any]]: ...


class StockPriceClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url or load_config().stock_api_url).rstrip("/")
        self.timeout = timeout

    def fetch_candles(
        self,
        symbol: str,
        *,
        interval: str,
        from_ts: int | None,
        to_ts: int | None,
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"interval": interval, "limit": limit}
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        url = f"{self.base_url}/candles/{symbol.upper()}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        data = payload.get("data", payload)
        if not isinstance(data, list):
            raise ValueError(f"Unexpected candles response for {symbol}")
        return data
