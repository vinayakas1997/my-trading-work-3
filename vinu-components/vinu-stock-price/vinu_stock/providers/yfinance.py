"""Yahoo Finance (yfinance) price provider — no API key required."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}


class YFinanceProvider:
    provider_id = "yfinance"

    def is_configured(self) -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            return False

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult:
        import yfinance as yf

        yf_interval = _INTERVAL_MAP.get(interval, "1d")
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%d")

        try:
            ticker = yf.Ticker(symbol.strip())
            df = ticker.history(start=start_dt, end=end_dt, interval=yf_interval)
        except Exception as exc:
            return FetchBarsResult(False, [], str(exc))

        if df.empty:
            return FetchBarsResult(False, [], "No data returned")

        bars: list[BarRecord] = []
        sym = symbol.strip().upper()
        for ts_idx, row in df.iterrows():
            bar_ts = int(ts_idx.timestamp())
            adj_factor = 1.0
            raw_vol = row.get("Volume", 0.0)
            vol = 0.0 if pd.isna(raw_vol) else float(raw_vol)
            bars.append(
                BarRecord(
                    symbol=sym,
                    provider=self.provider_id,
                    bar_ts=bar_ts,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=vol,
                    adj_factor=adj_factor,
                )
            )
        return FetchBarsResult(True, bars)

    def earliest_available(self, symbol: str) -> EarliestResult:
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol.strip())
            info = ticker.info or {}
            ts = info.get("firstTradeDateEpochUtc")
            if ts:
                return EarliestResult(True, int(ts))
        except Exception as exc:
            return EarliestResult(False, None, str(exc))
        return EarliestResult(False, None, "No firstTradeDateEpochUtc in info")
