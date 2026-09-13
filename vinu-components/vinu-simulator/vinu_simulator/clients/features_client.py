from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vinu_simulator.clients.base import BaseClient

LOG = logging.getLogger(__name__)


class FeaturesClient(BaseClient):
    def get_indicators(
        self,
        symbol: str,
        kinds: list[str],
        from_ts: int,
        to_ts: int,
        interval: str = "1d",
    ) -> pd.DataFrame | None:
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
        return df
