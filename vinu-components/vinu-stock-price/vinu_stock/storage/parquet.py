"""Parquet read/write for 1m OHLCV bars."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from vinu_stock.storage.models import BarRecord

_BAR_FIELDS = [
    ("symbol", pa.string()),
    ("provider", pa.string()),
    ("bar_ts", pa.int64()),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
    ("vwap", pa.float64()),
    ("trades", pa.int64()),
    ("adj_factor", pa.float64()),
]

_empty_table = pa.table({name: pa.array([], type=typ) for name, typ in _BAR_FIELDS})


def bars_to_table(bars: list[BarRecord]) -> pa.Table:
    if not bars:
        return _empty_table
    data = {
        name: pa.array([getattr(b, name) for b in bars], type=typ)
        for name, typ in _BAR_FIELDS
    }
    return pa.table(data)


def _dedupe_table(table: pa.Table) -> pa.Table:
    if table.num_rows <= 1:
        return table.sort_by("bar_ts")
    keys = list(zip(
        table.column("symbol").to_pylist(),
        table.column("provider").to_pylist(),
        table.column("bar_ts").to_pylist(),
    ))
    seen: dict[tuple[str, str, int], int] = {}
    for i, key in enumerate(keys):
        seen[key] = i
    if len(seen) == table.num_rows:
        return table.sort_by("bar_ts")
    keep = sorted(seen.values())
    return table.take(keep).sort_by("bar_ts")


def _read_existing(path: Path) -> pa.Table:
    if not path.is_file():
        return _empty_table
    return pq.read_table(path)


def write_bars(path: Path, table: pa.Table, *, merge: bool = True) -> int:
    """Write bars to parquet; merge+dedupe with existing file if merge=True."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if merge and path.is_file():
        existing = _read_existing(path)
        table = _dedupe_table(pa.concat_tables([existing, table]))
    pq.write_table(table, path, compression="zstd")
    return table.num_rows


def append_bars(path: Path, bars: list[BarRecord]) -> int:
    """Append bars to daily parquet files (no full-file rewrite).

    Each day gets its own parquet file, limiting merge scope to at most
    one trading day (~390 rows). DuckDB reads all files at query time.
    """
    if not bars:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)

    by_day: dict[str, list[BarRecord]] = defaultdict(list)
    for bar in bars:
        day_key = datetime.fromtimestamp(bar.bar_ts, tz=timezone.utc).strftime("%Y%m%d")
        by_day[day_key].append(bar)

    total = 0
    for day_key, day_bars in by_day.items():
        day_path = path.parent / f"{path.stem}_{day_key}.parquet"
        pq.write_table(bars_to_table(day_bars), day_path, compression="zstd")
        total += len(day_bars)

    return total


def read_bars(path: Path) -> pa.Table:
    """Read bars, including any daily incremental files created by append_bars."""
    tables: list[pa.Table] = []
    if path.is_file():
        tables.append(_read_existing(path))
    stem = path.stem
    for sibling in sorted(path.parent.glob(f"{stem}_*.parquet")):
        if sibling.name != path.name:
            tables.append(_read_existing(sibling))
    if not tables:
        return _empty_table
    combined = pa.concat_tables(tables)
    return _dedupe_table(combined)


def consolidate_live_shards(live_path: Path) -> int:
    """Consolidate daily shard files into the base live file.

    Reads the base file + all ``{stem}_*.parquet`` daily shards, deduplicates,
    writes everything back to the base file, and removes the shard files.

    Returns the number of rows written to the consolidated file, or 0 if no
    data existed.
    """
    parent = live_path.parent
    if not parent.is_dir():
        return 0

    shards = sorted(parent.glob(f"{live_path.stem}_*.parquet"))
    if not shards and not live_path.is_file():
        return 0

    table = read_bars(live_path)
    if table.num_rows == 0:
        return 0

    pq.write_table(table, live_path, compression="zstd")

    for shard in shards:
        try:
            shard.unlink()
        except OSError:
            pass

    return table.num_rows
