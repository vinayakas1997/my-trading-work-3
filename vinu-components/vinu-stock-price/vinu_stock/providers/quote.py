"""Latest NBBO quote provider (bid / ask / spread) for the liquidity gate.

Separate from the bars providers (`alpaca.py` etc.): bars are a historical
backfill + 1m ingest concern, a quote is a *right now* microstructure read used
only at order time by vinu-live's spread gate (how-to-make-it-live.md #13). It
never touches the Parquet store -- the caller (StockService.get_quote) puts a
short TTL cache in front so a burst of order-time checks collapses to one
upstream call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_infra.retry import http_get_with_retry

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuoteResult:
    success: bool
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    spread_bps: float = 0.0
    ts: float = 0.0  # UTC epoch seconds of the quote, 0.0 if unknown
    error: str = ""


def _parse_quote_ts(raw: str) -> float:
    """Alpaca sends RFC3339 with up to 9 fractional digits ('...T00:00:00.123456789Z');
    datetime.fromisoformat only takes 3 or 6. Trim to 6, then parse. 0.0 on any
    problem -- the ts is advisory (staleness logging), never a gate input."""
    if not raw:
        return 0.0
    try:
        s = raw.replace("Z", "+00:00")
        if "." in s:
            head, rest = s.split(".", 1)
            digits = ""
            tail = ""
            for i, ch in enumerate(rest):
                if ch.isdigit():
                    digits += ch
                else:
                    tail = rest[i:]
                    break
            s = f"{head}.{digits[:6]}{tail}"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


class AlpacaQuoteProvider:
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

    def get_quote(self, symbol: str) -> QuoteResult:
        sym = symbol.strip().upper()
        if not self.is_configured():
            return QuoteResult(False, sym, error="ALPACA_API_KEY/SECRET not set")
        url = (
            f"{self._config.alpaca_data_base_url.rstrip('/')}"
            f"/v2/stocks/{sym}/quotes/latest"
        )
        try:
            resp = http_get_with_retry(
                url,
                params={"feed": "iex"},
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT_SEC,
            )
            q = (resp.json() or {}).get("quote") or {}
            bid = float(q.get("bp", 0.0) or 0.0)
            ask = float(q.get("ap", 0.0) or 0.0)
            # bid<=0 / ask<=0 => no book (halted, pre-list); ask<bid => crossed
            # feed glitch. Either way there is no usable spread -- report the
            # failure and let the caller fail open.
            if bid <= 0.0 or ask <= 0.0 or ask < bid:
                return QuoteResult(
                    False, sym, bid=bid, ask=ask,
                    error="no valid two-sided quote",
                )
            mid = (bid + ask) / 2.0
            spread_bps = (ask - bid) / mid * 10_000.0
            return QuoteResult(
                True, sym, bid=bid, ask=ask, mid=mid,
                spread_bps=spread_bps, ts=_parse_quote_ts(q.get("t", "")),
            )
        except requests.RequestException as exc:
            return QuoteResult(False, sym, error=str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            return QuoteResult(False, sym, error=f"unparseable quote: {exc}")
