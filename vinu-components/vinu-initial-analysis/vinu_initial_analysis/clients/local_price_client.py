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
        return fetch_candles(
            self._data_root, symbol,
            interval=interval, from_ts=from_ts, to_ts=to_ts, limit=limit,
        )
