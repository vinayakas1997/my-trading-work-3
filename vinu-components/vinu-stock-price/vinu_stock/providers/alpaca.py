"""Alpaca market data bars provider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_infra.retry import http_get_with_retry
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)


def _parse_bar_row(sym: str, provider_id: str, row: dict) -> BarRecord:
    ts = row.get("t", "")
    if ts.endswith("Z"):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(ts)
    return BarRecord(
        symbol=sym,
        provider=provider_id,
        bar_ts=int(dt.timestamp()),
        open=float(row["o"]),
        high=float(row["h"]),
        low=float(row["l"]),
        close=float(row["c"]),
        volume=float(row.get("v", 0)),
        trades=int(row.get("n", 0)),
    )


class AlpacaProvider:
    provider_id = "alpaca"

    # Alpaca's /v2/stocks/bars accepts a comma-separated `symbols` list in one
    # request; this caps how many go in a single call so a large watchlist
    # still fetches in a handful of round-trips rather than one giant query
    # string. Mirrors the chunking vinu-screener's HttpStockDataSource.
    # get_ohlcv_batch already does for vinu-stock-price's own /candles/batch.
    MAX_BATCH_SYMBOLS = 200

    def __init__(self, config: VinuStockConfig | None = None) -> None:
        self._config = config or load_config()

    def is_configured(self) -> bool:
        return bool(self._config.alpaca_api_key and self._config.alpaca_api_secret)

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._config.alpaca_api_key,
            "APCA-API-SECRET-KEY": self._config.alpaca_api_secret,
        }

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult:
        if not self.is_configured():
            return FetchBarsResult(False, [], "ALPACA_API_KEY/SECRET not set")
        sym = symbol.strip().upper()
        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self._config.alpaca_data_base_url.rstrip('/')}/v2/stocks/bars"
        base_params: dict[str, str] = {
            "symbols": sym,
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
            "feed": "iex",
            # Without this, Alpaca returns raw prices: a split shows up as a
            # cliff in the OHLC series. "all" applies both split and dividend
            # adjustments server-side, so adj_factor can stay 1.0 downstream.
            "adjustment": "all",
        }
        try:
            all_bars: list[BarRecord] = []
            page_token: str | None = None
            while True:
                params = dict(base_params)
                if page_token:
                    params["page_token"] = page_token
                resp = http_get_with_retry(
                    url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT_SEC
                )
                data = resp.json()
                for row in (data.get("bars") or {}).get(sym) or []:
                    all_bars.append(_parse_bar_row(sym, self.provider_id, row))
                page_token = data.get("next_page_token")
                if not page_token:
                    break
            return FetchBarsResult(True, all_bars)
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))

    def fetch_bars_multi(
        self,
        symbols: list[str],
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> dict[str, FetchBarsResult]:
        """Batched equivalent of calling fetch_bars() once per symbol.

        Alpaca's /v2/stocks/bars natively accepts a comma-separated `symbols`
        param and returns one `bars` dict keyed by symbol, so N single-symbol
        HTTP calls (and their pagination loops) collapse into one call (per
        MAX_BATCH_SYMBOLS-sized chunk of symbols) covering all of them.
        Returns one FetchBarsResult per requested symbol, same shape/success
        semantics as fetch_bars.
        """
        syms = [s.strip().upper() for s in symbols if s.strip()]
        if not syms:
            return {}
        if not self.is_configured():
            err = "ALPACA_API_KEY/SECRET not set"
            return {s: FetchBarsResult(False, [], err) for s in syms}

        out: dict[str, FetchBarsResult] = {}
        for i in range(0, len(syms), self.MAX_BATCH_SYMBOLS):
            chunk = syms[i : i + self.MAX_BATCH_SYMBOLS]
            out.update(self._fetch_bars_multi_chunk(chunk, start_ts, end_ts))
        return out

    def _fetch_bars_multi_chunk(
        self,
        chunk: list[str],
        start_ts: int,
        end_ts: int,
    ) -> dict[str, FetchBarsResult]:
        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self._config.alpaca_data_base_url.rstrip('/')}/v2/stocks/bars"
        base_params: dict[str, str] = {
            "symbols": ",".join(chunk),
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
            "feed": "iex",
            "adjustment": "all",
        }
        bars_by_symbol: dict[str, list[BarRecord]] = {s: [] for s in chunk}
        try:
            page_token: str | None = None
            while True:
                params = dict(base_params)
                if page_token:
                    params["page_token"] = page_token
                resp = http_get_with_retry(
                    url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT_SEC
                )
                data = resp.json()
                bars_payload = data.get("bars") or {}
                for sym in chunk:
                    for row in bars_payload.get(sym) or []:
                        bars_by_symbol[sym].append(_parse_bar_row(sym, self.provider_id, row))
                page_token = data.get("next_page_token")
                if not page_token:
                    break
            return {s: FetchBarsResult(True, bars) for s, bars in bars_by_symbol.items()}
        except requests.RequestException as exc:
            err = str(exc)
            return {s: FetchBarsResult(False, [], err) for s in chunk}

    def earliest_available(self, symbol: str) -> EarliestResult:
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
        url = f"{self._config.alpaca_data_base_url.rstrip('/')}/v2/stocks/bars"
        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params: dict[str, str] = {
            "symbols": symbol.strip().upper(),
            "timeframe": "1Day",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
            "feed": "iex",
        }
        try:
            resp = http_get_with_retry(url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT_SEC)
            data = resp.json()
            bars = (data.get("bars") or {}).get(symbol.strip().upper()) or []
            if bars:
                ts = bars[0].get("t", "")
                if ts.endswith("Z"):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(ts)
                return EarliestResult(True, int(dt.timestamp()))
            return EarliestResult(False, None, "No bars returned")
        except requests.RequestException as exc:
            return EarliestResult(False, None, str(exc))
