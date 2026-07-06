from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from vinu_simulator.clients.base import BaseClient


class StrategyClient(BaseClient):
    def get_weights(
        self,
        strategy_name: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> pd.DataFrame:
        params: dict[str, Any] = {"strategy": strategy_name}
        if from_ts is not None:
            params["from_ts"] = from_ts
        if to_ts is not None:
            params["to_ts"] = to_ts
        data = self.get("/weights", params)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        pivot = df.pivot_table(
            index="date",
            columns="symbol",
            values="weight",
            aggfunc="first",
        ).fillna(0.0)
        return pivot.sort_index()

    def get_run_ids(self, strategy_name: str | None = None) -> list[str]:
        params = {}
        if strategy_name:
            params["strategy"] = strategy_name
        data = self.get("/runs", params)
        return [r["run_id"] for r in data] if data else []

    def list_strategies(self) -> list[dict[str, Any]]:
        return self.get("/strategies")
