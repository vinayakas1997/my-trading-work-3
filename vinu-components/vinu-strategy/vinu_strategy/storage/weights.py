from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SYMBOL_SCHEMA = pa.schema([
    pa.field("date", pa.timestamp("ms")),
    pa.field("symbol", pa.string()),
    pa.field("weight", pa.float64()),
    pa.field("signal_value", pa.float64()),
    pa.field("strategy_name", pa.string()),
    pa.field("run_id", pa.string()),
    pa.field("metadata", pa.string()),
])


class WeightStorage:
    def __init__(self, data_root: Path):
        self._data_root = data_root / "weights"
        self._data_root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, strategy_name: str, dt: datetime) -> Path:
        p = self._data_root / strategy_name / str(dt.year) / f"{dt.month:02d}"
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{dt.day:02d}.parquet"

    def append_weights(
        self,
        strategy_name: str,
        weights: dict[str, float],
        signal_values: dict[str, float] | None = None,
        run_id: str = "",
        metadata: dict | None = None,
    ) -> None:
        if not weights:
            return

        now = datetime.utcnow()
        path = self._path_for(strategy_name, now)

        rows = []
        for sym, w in weights.items():
            rows.append({
                "date": now,
                "symbol": sym,
                "weight": w,
                "signal_value": (signal_values or {}).get(sym, 0.0),
                "strategy_name": strategy_name,
                "run_id": run_id,
                "metadata": str(metadata or {}),
            })

        table = pa.Table.from_pylist(rows, schema=SYMBOL_SCHEMA)

        if path.exists():
            existing = pq.read_table(path)
            combined = pa.concat_tables([existing, table])
            pq.write_table(combined, path)
        else:
            pq.write_table(table, path)

    def _collect_tables(self, strategy_dir: Path) -> list[pa.Table]:
        tables = []
        for year_dir in sorted(strategy_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir():
                    continue
                for parquet_file in sorted(month_dir.glob("*.parquet")):
                    tables.append(pq.read_table(str(parquet_file)))
        return tables

    def read_weights(
        self,
        strategy_name: str,
        symbol: str | None = None,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> pd.DataFrame:
        strategy_dir = self._data_root / strategy_name
        if not strategy_dir.exists():
            return pd.DataFrame()

        tables = self._collect_tables(strategy_dir)

        if not tables:
            return pd.DataFrame()

        combined = pa.concat_tables(tables)
        df = combined.to_pandas()

        if symbol:
            df = df[df["symbol"] == symbol]
        if from_ts:
            df = df[df["date"] >= pd.to_datetime(from_ts, unit="s")]
        if to_ts:
            df = df[df["date"] <= pd.to_datetime(to_ts, unit="s")]

        return df.sort_values("date").reset_index(drop=True)

    def delete_weights(self, strategy_name: str, symbol: str | None = None) -> int:
        strategy_dir = self._data_root / strategy_name
        if not strategy_dir.exists():
            return 0
        deleted = 0
        for year_dir in list(strategy_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for month_dir in list(year_dir.iterdir()):
                if not month_dir.is_dir():
                    continue
                for parquet_file in list(month_dir.glob("*.parquet")):
                    if symbol is not None:
                        df = pq.read_table(str(parquet_file)).to_pandas()
                        before = len(df)
                        df = df[df["symbol"] != symbol]
                        removed = before - len(df)
                        if removed > 0:
                            if df.empty:
                                parquet_file.unlink()
                            else:
                                table = pa.Table.from_pandas(df, schema=SYMBOL_SCHEMA)
                                pq.write_table(table, parquet_file)
                            deleted += removed
                    else:
                        parquet_file.unlink()
                        deleted += 1
            for month_dir in list(year_dir.iterdir()):
                if month_dir.is_dir() and not any(month_dir.iterdir()):
                    month_dir.rmdir()
            if year_dir.is_dir() and not any(year_dir.iterdir()):
                year_dir.rmdir()
        if not symbol:
            strategy_dir_s = self._data_root / strategy_name
            if strategy_dir_s.exists() and not any(strategy_dir_s.iterdir()):
                strategy_dir_s.rmdir()
        return deleted
