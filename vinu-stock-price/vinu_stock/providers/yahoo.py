"""Yahoo Finance chart API provider (fallback / testing)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC, USER_AGENT
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)


def _symbol_to_yahoo(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s or "/" in s or "-" in s:
        return s
    return f"{s}"


class YahooProvider:
    provider_id = "yahoo"

    def is_configured(self) -> bool:
        return True

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult:
        yahoo_sym = _symbol_to_yahoo(symbol)
        yahoo_interval = "1m" if interval == "1m" else "1d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
        params = {
            "interval": yahoo_interval,
            "period1": start_ts,
            "period2": end_ts,
            "includePrePost": "false",
        }
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))

        bars = _parse_yahoo_chart(symbol, self.provider_id, data)
        return FetchBarsResult(True, bars)

    def earliest_available(self, symbol: str) -> EarliestResult:
        # Probe with a very wide daily range to find first timestamp
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = int(datetime(1990, 1, 1, tzinfo=timezone.utc).timestamp())
        result = self.fetch_bars(symbol, start_ts, end_ts, interval="1d")
        if not result.success or not result.bars:
            return EarliestResult(False, None, result.error or "No data")
        return EarliestResult(True, min(b.bar_ts for b in result.bars))


def _parse_yahoo_chart(symbol: str, provider: str, root: dict) -> list[BarRecord]:
    bars: list[BarRecord] = []
    chart = root.get("chart", {})
    if chart.get("error"):
        return bars
    results = chart.get("result") or []
    if not results:
        return bars
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators") or {}).get("quote", [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    sym = symbol.strip().upper()
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if o is None or h is None or l is None or c is None:
            continue
        vol = volumes[i] if i < len(volumes) and volumes[i] is not None else 0.0
        bars.append(
            BarRecord(
                symbol=sym,
                provider=provider,
                bar_ts=int(ts),
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(c),
                volume=float(vol),
            )
        )
    return bars
