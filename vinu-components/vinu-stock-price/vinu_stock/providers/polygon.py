"""Polygon.io aggregates API provider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_lib.retry import http_get_with_retry
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)


class PolygonProvider:
    provider_id = "polygon"

    def __init__(self, config: VinuStockConfig | None = None) -> None:
        self._config = config or load_config()

    def is_configured(self) -> bool:
        return bool(self._config.polygon_api_key)

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult:
        if not self.is_configured():
            return FetchBarsResult(False, [], "POLYGON_API_KEY not set")
        sym = symbol.strip().upper()
        start_ms = start_ts * 1000
        end_ms = end_ts * 1000
        poly_timespan, poly_multiplier = ("minute", 1) if interval == "1m" else ("day", 1)
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/{poly_multiplier}/{poly_timespan}"
            f"/{start_ms}/{end_ms}"
        )
        headers = {"Authorization": f"Bearer {self._config.polygon_api_key}"}
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}
        try:
            all_bars: list[BarRecord] = []
            while url:
                resp = http_get_with_retry(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
                data = resp.json()
                if data.get("status") not in ("OK", "DELAYED", None):
                    return FetchBarsResult(False, [], data.get("error", data.get("message", "API error")))
                for row in data.get("results") or []:
                    all_bars.append(
                        BarRecord(
                            symbol=sym,
                            provider=self.provider_id,
                            bar_ts=int(row["t"]) // 1000,
                            open=float(row["o"]),
                            high=float(row["h"]),
                            low=float(row["l"]),
                            close=float(row["c"]),
                            volume=float(row.get("v", 0)),
                            vwap=float(row.get("vw", 0)),
                            trades=int(row.get("n", 0)),
                        )
                    )
                next_url = data.get("next_url")
                if next_url:
                    url = next_url
                    params = {}
                else:
                    break
            return FetchBarsResult(True, all_bars)
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))

    def earliest_available(self, symbol: str) -> EarliestResult:
        if not self.is_configured():
            return EarliestResult(False, None, "POLYGON_API_KEY not set")
        sym = symbol.strip().upper()
        url = f"https://api.polygon.io/v3/reference/tickers/{sym}"
        headers = {"Authorization": f"Bearer {self._config.polygon_api_key}"}
        try:
            resp = http_get_with_retry(url, params={}, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
            data = resp.json()
            listing = (data.get("results") or {}).get("list_date")
            if listing:
                dt = datetime.strptime(listing, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return EarliestResult(True, int(dt.timestamp()))
        except (requests.RequestException, ValueError) as exc:
            LOG.debug("Polygon earliest lookup failed: %s", exc)
        # Fallback probe: daily bars from 1990 (~13k rows) instead of 1m (~10M)
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = int(datetime(1990, 1, 1, tzinfo=timezone.utc).timestamp())
        result = self.fetch_bars(symbol, start_ts, end_ts, interval="1d")
        if result.bars:
            return EarliestResult(True, min(b.bar_ts for b in result.bars))
        return EarliestResult(False, None, result.error or "No data")
