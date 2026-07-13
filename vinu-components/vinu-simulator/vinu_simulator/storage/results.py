from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from vinu_simulator.models.simulation import SimulationResult, TradeRecord

RESULT_SCHEMA = pa.schema([
    pa.field("date", pa.timestamp("ms")),
    pa.field("portfolio_value", pa.float64()),
    pa.field("daily_return", pa.float64()),
])

TRADE_SCHEMA = pa.schema([
    pa.field("date", pa.timestamp("ms")),
    pa.field("symbol", pa.string()),
    pa.field("side", pa.string()),
    pa.field("shares", pa.float64()),
    pa.field("price", pa.float64()),
    pa.field("cost", pa.float64()),
    pa.field("weight_before", pa.float64()),
    pa.field("weight_after", pa.float64()),
])


class ResultStorage:
    def __init__(self, data_root: Path):
        self._data_root = data_root / "simulations"
        self._data_root.mkdir(parents=True, exist_ok=True)

    def _ensure_result_dir(self, run_id: str) -> Path:
        p = self._data_root / run_id[:2] / run_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _result_path(self, run_id: str) -> Path:
        return self._data_root / run_id[:2] / run_id

    def save(self, result: SimulationResult) -> None:
        rdir = self._ensure_result_dir(result.run_id)

        equity = result.portfolio_values.to_frame("portfolio_value").reset_index()
        equity.columns = ["date", "portfolio_value"]
        equity["daily_return"] = result.daily_returns.reindex(
            equity["date"]
        ).fillna(0.0).values
        equity["date"] = pd.to_datetime(equity["date"])

        table = pa.Table.from_pandas(equity, schema=RESULT_SCHEMA, preserve_index=False)
        pq.write_table(table, rdir / "equity.parquet")

        weights = result.weights_history.reset_index()
        weights.columns = ["date"] + list(result.weights_history.columns)
        weights.to_parquet(rdir / "weights.parquet")

        if result.trades:
            rows = [
                {
                    "date": t.date,
                    "symbol": t.symbol,
                    "side": t.side,
                    "shares": t.shares,
                    "price": t.price,
                    "cost": t.cost,
                    "weight_before": t.weight_before,
                    "weight_after": t.weight_after,
                }
                for t in result.trades
            ]
            trade_table = pa.Table.from_pylist(rows, schema=TRADE_SCHEMA)
            pq.write_table(trade_table, rdir / "trades.parquet")

        meta = {
            "strategy_name": result.strategy_name,
            "run_id": result.run_id,
            "timestamp": result.timestamp.isoformat(),
        }
        (rdir / "meta.json").write_text(json.dumps(meta, indent=2))

    def load_equity(self, run_id: str) -> pd.DataFrame:
        p = self._result_path(run_id) / "equity.parquet"
        if not p.exists():
            return pd.DataFrame()
        return pd.read_parquet(p)

    def load_weights(self, run_id: str) -> pd.DataFrame:
        p = self._result_path(run_id) / "weights.parquet"
        if not p.exists():
            return pd.DataFrame()
        return pd.read_parquet(p)

    def load_trades(self, run_id: str) -> list[TradeRecord]:
        p = self._result_path(run_id) / "trades.parquet"
        if not p.exists():
            return []
        df = pd.read_parquet(p)
        return [
            TradeRecord(
                date=row.date,
                symbol=row.symbol,
                side=row.side,
                shares=row.shares,
                price=row.price,
                cost=row.cost,
                weight_before=row.weight_before,
                weight_after=row.weight_after,
            )
            for row in df.itertuples()
        ]

    def load_meta(self, run_id: str) -> dict[str, Any] | None:
        p = self._result_path(run_id) / "meta.json"
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def delete(self, run_id: str) -> bool:
        rdir = self._result_path(run_id)
        if not rdir.exists():
            return False
        import shutil
        shutil.rmtree(rdir)
        return True
