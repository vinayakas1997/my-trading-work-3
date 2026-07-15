"""Tushare Pro price provider — Chinese A-share market data.

Requires TUSHARE_TOKEN environment variable.
Uses direct HTTP to api.tushare.pro (avoids fragile package dependency).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.retry import http_post_with_retry
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)

TUSHARE_API_URL = "https://api.tushare.pro"
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")


class TushareProvider:
    provider_id = "tushare"

    def is_configured(self) -> bool:
        return bool(TUSHARE_TOKEN)

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult:
        if interval != "1d":
            return FetchBarsResult(False, [], "Tushare only supports daily bars via this provider")
        if not self.is_configured():
            return FetchBarsResult(False, [], "TUSHARE_TOKEN not set")

        start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y%m%d")
        end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y%m%d")

        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {
                "ts_code": symbol.strip(),
                "start_date": start_date,
                "end_date": end_date,
            },
        }

        try:
            resp = http_post_with_retry(
                TUSHARE_API_URL,
                json=payload,
                timeout=30,
            )
            data = resp.json()
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))

        if data.get("code") != 0:
            msg = data.get("msg", "Unknown tushare error")
            return FetchBarsResult(False, [], msg)

        items = (data.get("data") or {}).get("items") or []
        fields = (data.get("data") or {}).get("fields") or []

        if not items:
            return FetchBarsResult(False, [], "No data returned")

        bars: list[BarRecord] = []
        sym = symbol.strip().upper()
        for item in items:
            record = dict(zip(fields, item))
            bar_ts = int(
                datetime.strptime(record["trade_date"], "%Y%m%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            bars.append(
                BarRecord(
                    symbol=sym,
                    provider=self.provider_id,
                    bar_ts=bar_ts,
                    open=float(record.get("open", 0.0)),
                    high=float(record.get("high", 0.0)),
                    low=float(record.get("low", 0.0)),
                    close=float(record.get("close", 0.0)),
                    volume=float(record.get("vol", 0.0)),
                    adj_factor=1.0,
                )
            )
        return FetchBarsResult(True, bars)

    def earliest_available(self, symbol: str) -> EarliestResult:
        if not self.is_configured():
            return EarliestResult(False, None, "TUSHARE_TOKEN not set")

        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {
                "ts_code": symbol.strip(),
                "start_date": "19900101",
                "end_date": "19900101",
                "limit": 1,
            },
        }

        try:
            resp = http_post_with_retry(TUSHARE_API_URL, json=payload, timeout=30)
            data = resp.json()
        except requests.RequestException as exc:
            return EarliestResult(False, None, str(exc))

        if data.get("code") != 0:
            return EarliestResult(False, None, data.get("msg", "Unknown error"))

        items = (data.get("data") or {}).get("items") or []
        fields = (data.get("data") or {}).get("fields") or []

        for item in items:
            record = dict(zip(fields, item))
            ts = int(
                datetime.strptime(record["trade_date"], "%Y%m%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            return EarliestResult(True, ts)

        return EarliestResult(False, None, "No earliest date available")
