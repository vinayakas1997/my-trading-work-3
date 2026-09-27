from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vinu_simulator.clients._cache import LRUCache
from vinu_simulator.clients.base import BaseClient

LOG = logging.getLogger(__name__)


class FeaturesClient(BaseClient):
    def __init__(self, base_url: str, timeout: float = 30.0, cache_maxsize: int = 256):
        super().__init__(base_url, timeout=timeout)
        # item #13 finding #4: same repeated-identical-fetch gap as
        # PriceClient -- a sweep re-requesting the same symbol/kind/range
        # otherwise re-fetches from the network every time.
        self._cache = LRUCache(maxsize=cache_maxsize)

    def get_indicators(
        self,
        symbol: str,
        kinds: list[str],
        from_ts: int,
        to_ts: int,
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        cache_key = (symbol, tuple(sorted(kinds)), from_ts, to_ts, interval)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        params: dict[str, Any] = {
            "kinds": ",".join(kinds),
            "from": from_ts,
            "to": to_ts,
            "interval": interval,
        }
        try:
            data = self.get(f"/indicators/{symbol}", params)
        except Exception as e:
            # #32: this silently drops the indicator column from custom_sim.py's
            # merge, which can then trip the generate_weights crash-fallback if
            # the strategy references it -- log clearly so that's diagnosable
            # instead of indistinguishable from "no indicators requested".
            LOG.warning("get_indicators failed for %s (kinds=%s): %s", symbol, kinds, e)
            return None
        if not data or not isinstance(data, list):
            return None
        df = pd.DataFrame(data)
        if df.empty:
            return None
        df["ts"] = pd.to_datetime(df["ts"], unit="s")
        df = df.set_index("ts").sort_index()
        drop_cols = [c for c in ["symbol", "ts"] if c in df.columns]
        df = df.drop(columns=drop_cols, errors="ignore")
        self._cache.set(cache_key, df)
        return df.copy()
