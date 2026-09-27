"""Yahoo Finance (yfinance) price provider — no API key required."""

from __future__ import annotations

import logging
import time
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

# item #19 finding #4: every other provider in this directory (yahoo.py,
# polygon.py, alpaca.py, tushare.py, finnhub_provider.py) routes through
# vinu_infra.retry's shared helper; this one had no retry/backoff at all.
# Same convention item #11 finding #3 already established for
# vinu-agent's fundamentals_tool.py -- a plain retry-after-sleep loop,
# not vinu_infra.retry's HTTP helper, since its `exceptions=` tuple is
# requests-specific and wouldn't reliably match yfinance's own transient
# failure modes.
_FETCH_RETRIES = 3
_RETRY_SLEEP_SEC = 1.0


def _retry(fn):
    """Call `fn()` up to `_FETCH_RETRIES` times, sleeping between attempts
    on any exception. Re-raises the last exception if every attempt fails."""
    last_exc: Exception | None = None
    for attempt in range(1, _FETCH_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < _FETCH_RETRIES:
                LOG.warning(
                    "yfinance fetch attempt %d/%d failed, retrying after %.1fs: %s",
                    attempt, _FETCH_RETRIES, _RETRY_SLEEP_SEC, exc,
                )
                time.sleep(_RETRY_SLEEP_SEC)
    raise last_exc


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
            df = _retry(lambda: yf.Ticker(symbol.strip()).history(
                start=start_dt, end=end_dt, interval=yf_interval,
            ))
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
            info = _retry(lambda: yf.Ticker(symbol.strip()).info) or {}
            ts = info.get("firstTradeDateEpochUtc")
            if ts:
                return EarliestResult(True, int(ts))
        except Exception as exc:
            return EarliestResult(False, None, str(exc))
        return EarliestResult(False, None, "No firstTradeDateEpochUtc in info")
