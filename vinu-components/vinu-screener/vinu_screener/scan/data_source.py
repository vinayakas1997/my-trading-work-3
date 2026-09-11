"""Data access the scan loop needs, kept behind a small `Protocol` so
`monitor.py` (B6) never depends on a specific HTTP client or service —
tests use a plain in-memory stub, and swapping the real backend later
never touches the loop itself.

`HttpStockDataSource` is the real adapter: `vinu-stock-price` has no bulk
multi-symbol endpoint (confirmed by reading its routes before writing this
— only `GET /candles/{symbol}`, one call per symbol), so a scan cycle
really is one HTTP call per symbol in the (coarse-filtered) universe.
That's exactly why B9's timeout guard and B6's rate-limit-floored interval
matter — this is not a hypothetical scaling concern, it's what the
upstream service's actual shape requires.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import pandas as pd


class SymbolDataSource(Protocol):
    def get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        """Return an OHLCV frame (columns at least `open`/`high`/`low`/
        `close`/`volume`, oldest row first) for `symbol`, or `None` if
        there's no usable data (unknown symbol, empty history, etc.) --
        never raises; a data gap is a `None`, not an exception."""
        ...

    def get_snapshot(self, symbol: str) -> dict[str, float] | None:
        """Cheap last-bar fields for B7's coarse filter -- `price`,
        `volume`, `dollar_volume`. `None` on no data, same contract as
        `get_ohlcv`."""
        ...


class HttpStockDataSource:
    """Talks to vinu-stock-price's `GET /candles/{symbol}` (the same
    endpoint + response shape `vinu_research.tools.ResearchTools.
    get_benchmark_data` already reads, confirmed by reading that call site
    before writing this) via an injected `httpx`-like client so tests never
    need a real network call."""

    def __init__(self, client, *, base_url: str, days: int = 250, interval: str = "1d") -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._days = days
        self._interval = interval

    def _fetch(self, symbol: str) -> list[dict] | None:
        try:
            resp = self._client.get(
                f"{self._base_url}/candles/{symbol.upper()}",
                params={"interval": self._interval, "days": self._days, "adjusted": True},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None
        rows = data.get("data") if isinstance(data, dict) else None
        return rows or None

    def get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        rows = self._fetch(symbol)
        if not rows:
            return None
        try:
            df = pd.DataFrame(rows)
            if "close" not in df.columns:
                return None
            if "bar_ts" in df.columns:
                df.index = pd.to_datetime(df["bar_ts"], unit="s", utc=True)
            for col in ("open", "high", "low", "close", "volume"):
                if col not in df.columns:
                    df[col] = df.get("close", pd.Series(dtype=float))
            return df[["open", "high", "low", "close", "volume"]].astype(float)
        except Exception:
            return None

    def get_snapshot(self, symbol: str) -> dict[str, float] | None:
        df = self.get_ohlcv(symbol)
        if df is None or df.empty:
            return None
        last = df.iloc[-1]
        price = float(last["close"])
        volume = float(last["volume"])
        return {"price": price, "volume": volume, "dollar_volume": price * volume}


def utcnow_ts() -> float:
    return datetime.now(timezone.utc).timestamp()
