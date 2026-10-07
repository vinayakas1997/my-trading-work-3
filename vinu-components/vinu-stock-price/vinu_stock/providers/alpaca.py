"""Alpaca market data bars provider."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

from vinu_infra.sessions import OVERNIGHT, session_of
from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_infra.retry import http_get_with_retry
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)

OVERNIGHT_DELAY_MINUTES = 16


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

    @staticmethod
    def overnight_feed() -> str:
        """The Alpaca feed that carries the overnight session (20:00-04:00 ET, Blue Ocean venue): `boats`. The default IEX
        feed has essentially no trades then. Empty (VINU_STOCK_OVERNIGHT_FEED=) switches overnight bars off."""
        return os.environ.get("VINU_STOCK_OVERNIGHT_FEED", "boats").strip()

    def _fetch_overnight(self, symbols: list[str], start_iso: str, end_iso: str) -> dict[str, list[BarRecord]]:
        """Overnight-session 1m bars for `symbols`, only those whose open time is really in the overnight session (the
        other sessions come from the main feed, so nothing is double counted). Never raises: a failure here costs the
        overnight bars of this fetch, not the regular-session bars the caller already has."""
        feed = self.overnight_feed()
        out: dict[str, list[BarRecord]] = {s: [] for s in symbols}
        if not feed:
            return out
        # The plan delays this feed by 15 minutes and answers 403 to a window that reaches into them, so stop short of now.
        latest = datetime.now(timezone.utc) - timedelta(minutes=OVERNIGHT_DELAY_MINUTES)
        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        if end_dt > latest:
            end_iso = latest.strftime("%Y-%m-%dT%H:%M:%SZ")
        if datetime.fromisoformat(start_iso.replace("Z", "+00:00")) >= datetime.fromisoformat(end_iso.replace("Z", "+00:00")):
            return out
        url = f"{self._config.alpaca_data_base_url.rstrip('/')}/v2/stocks/bars"
        base = {"symbols": ",".join(symbols), "timeframe": "1Min", "start": start_iso, "end": end_iso, "limit": "10000",
                "feed": feed, "adjustment": "all"}
        try:
            token: str | None = None
            while True:
                params = dict(base)
                if token:
                    params["page_token"] = token
                data = http_get_with_retry(url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT_SEC).json()
                for sym, rows in (data.get("bars") or {}).items():
                    for row in rows or []:
                        bar = _parse_bar_row(sym, self.provider_id, row)
                        if session_of(bar.bar_ts) == OVERNIGHT and sym in out:
                            out[sym].append(bar)
                token = data.get("next_page_token")
                if not token:
                    break
        except Exception as exc:  # noqa: BLE001 -- see the docstring
            LOG.warning("Alpaca overnight bars (%s feed) unavailable for %s..: %s", feed, symbols[:3], exc)
            return {s: [] for s in symbols}
        return out

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
            all_bars.extend(self._fetch_overnight([sym], start_iso, end_iso).get(sym, []))
            all_bars.sort(key=lambda b: b.bar_ts)
            return FetchBarsResult(True, all_bars)
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            # Malformed/partial JSON from Alpaca (missing o/h/l/c, truncated
            # body, etc.) -- treat it the same as a network failure: this
            # fetch failed cleanly instead of raising out of the provider.
            LOG.warning("Alpaca fetch_bars(%s): malformed response: %s", sym, exc)
            return FetchBarsResult(False, [], f"malformed response: {exc}")

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
            for sym, extra in self._fetch_overnight(chunk, start_iso, end_iso).items():
                bars_by_symbol[sym].extend(extra)
                bars_by_symbol[sym].sort(key=lambda b: b.bar_ts)
            return {s: FetchBarsResult(True, bars) for s, bars in bars_by_symbol.items()}
        except requests.RequestException as exc:
            err = str(exc)
            return {s: FetchBarsResult(False, [], err) for s in chunk}
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            # Malformed/partial JSON from Alpaca -- fail this chunk cleanly
            # (same shape as a network failure) instead of raising out of
            # the provider and taking the whole batch fetch down with it.
            LOG.warning("Alpaca fetch_bars_multi(%s): malformed response: %s", chunk, exc)
            err = f"malformed response: {exc}"
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
