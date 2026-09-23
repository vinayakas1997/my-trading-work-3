"""A local, no-HTTP-server-needed adapter satisfying the same interface
`peer_relative_strength` expects from `price_client` (`get_watchlist()` /
`get_candles()`) as the real `PriceClient` (`price_client.py`, which hits
the live stock-price HTTP API).

Backed by `vinu_stock.query.engine.fetch_candles()` reading real cached
bars directly off disk -- the same function already used elsewhere in
this project to fetch real AAPL/JNJ/TSLA data without a running service.
`get_watchlist()` returns exactly the peer symbols this instance was
constructed with (the batch's own real symbol list minus the queried
symbol), not an open-ended live watchlist -- correct for orchestrator use,
where the "peer universe" for a batch run is exactly the batch's own
symbols.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_stock.query.engine import fetch_candles

from .price_client import _INTERVAL_MAP


class LocalPriceClient:
    def __init__(self, data_root: Path | str, symbols: list[str]):
        self._data_root = Path(data_root)
        self._symbols = list(symbols)

    def get_watchlist(self) -> list[str]:
        return list(self._symbols)

    def get_candles(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str = "1D",
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        # Real bug found 2026-09-23: this passed `interval` straight through
        # unmapped -- every angle time_format string except "1H"/"4H"/"1D"
        # (which happen to lowercase into what vinu-stock-price's
        # interval_to_seconds() accepts) would raise "Unsupported interval"
        # inside fetch_candles, e.g. "1min"/"5min"/"15min"/"1W"/"1M"/"6M".
        # Reuses the exact same real->vinu-stock-price mapping `PriceClient`
        # (the HTTP sibling of this client) uses, so the two clients can't
        # drift on what a given time_format string actually resolves to.
        mapped = _INTERVAL_MAP.get(interval, interval)
        return fetch_candles(
            self._data_root, symbol,
            interval=mapped, from_ts=from_ts, to_ts=to_ts, limit=limit,
        )
