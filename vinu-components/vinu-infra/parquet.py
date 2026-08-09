"""Shared Parquet store with append, dedup, and partition helpers.

Usage:
    from vinu_infra.parquet import ParquetStore

    store = ParquetStore("/data/parquet")
    store.append("AAPL/2026.parquet", records, dedup_on=["article_id"])
    table = store.read("AAPL/2026.parquet")
    table = store.read_shard("live/AAPL_*.parquet")
    store.consolidate("live/AAPL_*.parquet", "archive/AAPL_2026.parquet", dedup_on=["id"])
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
        """Reads the entire existing file at `rel_path` (if any), concats
        the new records, and rewrites the whole file -- cost is O(existing
        file size), not O(len(records)). Fine for occasional/batch calls.
        NOT safe to call repeatedly on the same `rel_path` at high
        frequency (e.g. once per live-ingest tick) -- each call re-reads
        and re-writes everything written so far, making total cost grow
        quadratically with the number of calls. For that pattern, write
        each batch to its own shard path instead (e.g. a timestamped
        filename) and periodically call `consolidate()` on the shard glob
        -- the module docstring's own example already shows this split
        (`append()` on one coarse path vs. `read_shard()`/`consolidate()`
        on a `live/*.parquet` glob)."""
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

    def read_shard(
        self,
        rel_glob: str,
        dedup_on: list[str] | None = None,
    ) -> pa.Table | None:
        matching = sorted(self._root.glob(rel_glob))
        if not matching:
            return None
        tables = []
        for p in matching:
            try:
                tbl = pq.read_table(p)
                tables.append(tbl)
            except Exception:
                continue
        if not tables:
            return None
        combined = pa.concat_tables(tables)
        if dedup_on:
            combined = _dedup_table(combined, dedup_on)
        return combined

    def consolidate(
        self,
        shard_glob: str,
        output_rel_path: str,
        dedup_on: list[str] | None = None,
    ) -> int:
        shards = sorted(self._root.glob(shard_glob))
        if not shards:
            return 0
        tables = []
        for p in shards:
            try:
                tbl = pq.read_table(p)
                tables.append(tbl)
            except Exception:
                continue
        if not tables:
            return 0
        combined = pa.concat_tables(tables)
        if dedup_on:
            combined = _dedup_table(combined, dedup_on)
        output_path = self._resolve(output_rel_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(combined, output_path)
        for shard in shards:
            try:
                shard.unlink()
            except OSError:
                pass
        return combined.num_rows

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
