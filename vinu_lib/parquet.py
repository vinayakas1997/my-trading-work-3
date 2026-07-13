"""Shared Parquet store with append, dedup, and partition helpers.

Usage:
    from vinu_lib.parquet import ParquetStore

    store = ParquetStore("/data/parquet")
    store.append("AAPL/2026.parquet", records, dedup_on=["article_id"])
    table = store.read("AAPL/2026.parquet")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


class ParquetStore:
    def __init__(self, data_root: str | Path) -> None:
        self._root = Path(data_root)

    def _resolve(self, rel_path: str) -> Path:
        return self._root / rel_path

    def append(
        self,
        rel_path: str,
        records: list[dict[str, Any]],
        schema: pa.Schema | None = None,
        dedup_on: list[str] | None = None,
    ) -> None:
        if not records:
            return
        table = pa.Table.from_pylist(records, schema=schema)
        path = self._resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read(path)
        if existing is not None:
            combined = pa.concat_tables([existing, table])
            if dedup_on:
                combined = _dedup_table(combined, dedup_on)
            pq.write_table(combined, path)
        else:
            pq.write_table(table, path)

    def read(self, rel_path: str) -> pa.Table | None:
        path = self._resolve(rel_path)
        return self._read(path)

    def _read(self, path: Path) -> pa.Table | None:
        if path.is_file():
            try:
                return pq.read_table(path)
            except Exception:
                return None
        return None

    def compact(self, rel_path: str) -> None:
        table = self.read(rel_path)
        if table is not None:
            pq.write_table(table, self._resolve(rel_path))


def _dedup_table(table: pa.Table, on: list[str]) -> pa.Table:
    import pandas as pd
    df = table.to_pandas()
    if df.empty:
        return table
    df = df.drop_duplicates(subset=on, keep="last")
    return pa.Table.from_pandas(df, schema=table.schema)
