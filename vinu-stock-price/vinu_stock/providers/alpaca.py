"""Alpaca market data bars provider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.base import EarliestResult, FetchBarsResult
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_stock.storage.models import BarRecord

LOG = logging.getLogger(__name__)


class AlpacaProvider:
    provider_id = "alpaca"

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
        params: dict[str, str] = {
            "symbols": sym,
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
        }
        try:
            all_bars: list[BarRecord] = []
            page_token: str | None = None
            while True:
                if page_token:
                    params["page_token"] = page_token
                resp = requests.get(
                    url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT_SEC
                )
                resp.raise_for_status()
                data = resp.json()
                for row in (data.get("bars") or {}).get(sym) or []:
                    ts = row.get("t", "")
                    if ts.endswith("Z"):
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromisoformat(ts)
                    all_bars.append(
                        BarRecord(
                            symbol=sym,
                            provider=self.provider_id,
                            bar_ts=int(dt.timestamp()),
                            open=float(row["o"]),
                            high=float(row["h"]),
                            low=float(row["l"]),
                            close=float(row["c"]),
                            volume=float(row.get("v", 0)),
                            trades=int(row.get("n", 0)),
                        )
                    )
                page_token = data.get("next_page_token")
                if not page_token:
                    break
            return FetchBarsResult(True, all_bars)
        except requests.RequestException as exc:
            return FetchBarsResult(False, [], str(exc))

    def earliest_available(self, symbol: str) -> EarliestResult:
        # Alpaca 1m history is limited; probe with a wide window
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = end_ts - 365 * 24 * 3600
        result = self.fetch_bars(symbol, start_ts, end_ts)
        if result.bars:
            return EarliestResult(True, min(b.bar_ts for b in result.bars))
        return EarliestResult(False, None, result.error or "No data")
