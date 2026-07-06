from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from vinu_correlation.storage.models import IMPACT_SCHEMA, BASELINE_SCHEMA, CORRELATION_SCHEMA
from vinu_correlation.storage.paths import impact_path, baseline_path, correlation_path, symbol_dir

LOG = logging.getLogger(__name__)


class CorrelationStorage:
    def __init__(self, data_root: Path):
        self._data_root = data_root

    # ------------------------------------------------------------------
    # Impact events
    # ------------------------------------------------------------------

    def get_last_computed_ts(self, symbol: str) -> int | None:
        path = symbol_dir(self._data_root, symbol)
        if not path.is_dir():
            return None
        parquet_files = sorted(path.glob("*.parquet"))
        if not parquet_files:
            return None
        con = duckdb.connect()
        try:
            latest = None
            for f in parquet_files:
                if f.stem.endswith("_baseline") or f.stem.endswith("_correlation"):
                    continue
                try:
                    df = con.execute(f"SELECT max(ts) as max_ts FROM read_parquet('{f}')").fetchone()
                    if df and df[0] is not None:
                        val = int(df[0])
                        if latest is None or val > latest:
                            latest = val
                except Exception:
                    continue
            return latest
        finally:
            con.close()

    def append_events(self, symbol: str, events: list[dict[str, Any]]):
        if not events:
            return
        table = pa.Table.from_pylist(events, schema=IMPACT_SCHEMA)
        year = _year_from_ts(events[0]["ts"])
        path = impact_path(self._data_root, symbol, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_existing(path)
        if existing is not None:
            combined = pa.concat_tables([existing, table])
            combined = _dedup_by_article_id(combined)
            pq.write_table(combined, path)
        else:
            pq.write_table(table, path)

    def read_events(self, symbol: str, year: int) -> pa.Table | None:
        path = impact_path(self._data_root, symbol, year)
        return self._read_existing(path)

    def read_events_range(self, symbol: str, from_ts: int, to_ts: int) -> pa.Table | None:
        con = duckdb.connect()
        try:
            sym_dir = symbol_dir(self._data_root, symbol)
            if not sym_dir.is_dir():
                return None
            impact_files = [str(p) for p in sym_dir.glob("[0-9]*.parquet")
                            if not p.stem.endswith("_baseline") and not p.stem.endswith("_correlation")]
            if not impact_files:
                return None
            glob_pattern = str(sym_dir / "*.parquet")
            result = con.execute(
                f"""
                SELECT * FROM read_parquet({glob_pattern!r})
                WHERE symbol = ? AND ts >= ? AND ts <= ?
                """,
                [symbol, from_ts, to_ts]
            ).fetch_arrow_table()
            return result if result.num_rows > 0 else None
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------

    def append_baselines(self, symbol: str, baselines: list[dict[str, Any]]):
        if not baselines:
            return
        table = pa.Table.from_pylist(baselines, schema=BASELINE_SCHEMA)
        year = _year_from_ts(baselines[0]["hour_ts"])
        path = baseline_path(self._data_root, symbol, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_existing(path)
        if existing is not None:
            combined = pa.concat_tables([existing, table])
            pq.write_table(combined, path)
        else:
            pq.write_table(table, path)

    # ------------------------------------------------------------------
    # Correlation matrices
    # ------------------------------------------------------------------

    def append_correlations(self, symbol: str, correlations: list[dict[str, Any]]):
        if not correlations:
            return
        table = pa.Table.from_pylist(correlations, schema=CORRELATION_SCHEMA)
        year = _year_from_ts(correlations[0]["period_start"])
        path = correlation_path(self._data_root, symbol, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_existing(path)
        if existing is not None:
            combined = pa.concat_tables([existing, table])
            pq.write_table(combined, path)
        else:
            pq.write_table(table, path)

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self, symbol: str, year: int, force: bool = False):
        imp_path = impact_path(self._data_root, symbol, year)
        existing = self._read_existing(imp_path)
        if existing is not None:
            pq.write_table(existing, imp_path)
        base_path = baseline_path(self._data_root, symbol, year)
        existing_base = self._read_existing(base_path)
        if existing_base is not None:
            pq.write_table(existing_base, base_path)
        corr_path = correlation_path(self._data_root, symbol, year)
        existing_corr = self._read_existing(corr_path)
        if existing_corr is not None:
            pq.write_table(existing_corr, corr_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_existing(self, path: Path) -> pa.Table | None:
        if path.is_file():
            try:
                return pq.read_table(path)
            except Exception:
                return None
        return None


def _year_from_ts(ts: int) -> int:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).year


def _dedup_by_article_id(table: pa.Table) -> pa.Table:
    import pandas as pd
    df = table.to_pandas()
    if df.empty:
        return table
    df = df.sort_values("computed_at", ascending=False).drop_duplicates(
        subset=["article_id", "symbol"], keep="first"
    )
    return pa.Table.from_pandas(df, schema=table.schema)
