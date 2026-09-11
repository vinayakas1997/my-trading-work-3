"""Data access the scan loop needs, kept behind a small `Protocol` so
`monitor.py` (B6) never depends on a specific HTTP client or service —
tests use a plain in-memory stub, and swapping the real backend later
never touches the loop itself.

`HttpStockDataSource` is the real adapter, talking to `vinu-stock-price`.
Originally this only had `GET /candles/{symbol}` to call (confirmed by
reading its routes before writing this), so a scan cycle really was one
HTTP call per symbol in the (coarse-filtered) universe -- exactly why B9's
timeout guard and B6's rate-limit-floored interval matter. `vinu-stock-price`
has since grown `POST /candles/batch` (the bulk-endpoint gap this file's
own comment used to flag); `get_ohlcv_batch()` below calls it, and
`ScanMonitor.run_cycle()` (B6) uses it automatically when a data source
exposes it (duck-typed `hasattr`, so a data source without a batch method --
the tests' `FakeDataSource`, or a future non-HTTP source -- still works
unmodified via the original one-call-per-symbol path). The timeout guard
and rate-limit floor stay in place regardless: a batch call over a very
large universe is still one slow round-trip that must not be allowed to
hang the whole cycle.
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

    # get_ohlcv_batch is intentionally NOT part of this Protocol -- it's an
    # optional capability `ScanMonitor` detects via `hasattr()`, not a
    # required method every SymbolDataSource must implement (the in-memory
    # test stubs, and any future source with no natural bulk shape, are
    # still fully conformant without it).


class HttpStockDataSource:
    """Talks to vinu-stock-price's `GET /candles/{symbol}` (the same
    endpoint + response shape `vinu_research.tools.ResearchTools.
    get_benchmark_data` already reads, confirmed by reading that call site
    before writing this) via an injected `httpx`-like client so tests never
    need a real network call."""

    # Matches vinu-stock-price's own StockService.MAX_BATCH_SYMBOLS cap --
    # duplicated here (not imported: this package has no dependency on
    # vinu-stock-price's code, only its HTTP contract) so a universe larger
    # than one server-side batch call allows is split into several batch
    # calls rather than one oversized request the server would reject.
    BATCH_CHUNK_SIZE = 500

    def __init__(self, client, *, base_url: str, days: int = 250, interval: str = "1d") -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._days = days
        self._interval = interval

    def _rows_to_ohlcv(self, rows: list[dict] | None) -> pd.DataFrame | None:
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

    def get_ohlcv_batch(self, symbols: list[str]) -> dict[str, pd.DataFrame | None]:
        """One `POST /candles/batch` call per `BATCH_CHUNK_SIZE`-sized chunk
        of `symbols`, instead of one `GET /candles/{symbol}` call each.
        Every requested symbol gets an entry in the result -- `None` for
        any symbol the server had no data for, or if the whole batch call
        failed (never raises; a fully-failed chunk degrades every symbol
        in it to `None`, same as a single failed `get_ohlcv` call would)."""
        out: dict[str, pd.DataFrame | None] = {}
        for i in range(0, len(symbols), self.BATCH_CHUNK_SIZE):
            chunk = symbols[i : i + self.BATCH_CHUNK_SIZE]
            try:
                resp = self._client.post(
                    f"{self._base_url}/candles/batch",
                    json={"symbols": chunk, "interval": self._interval, "days": self._days, "adjusted": True},
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", {}) if isinstance(data, dict) else {}
            except Exception:
                results = {}
            for symbol in chunk:
                entry = results.get(symbol.upper())
                rows = entry.get("data") if isinstance(entry, dict) else None
                out[symbol.upper()] = self._rows_to_ohlcv(rows)
        return out

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
        return self._rows_to_ohlcv(self._fetch(symbol))

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
