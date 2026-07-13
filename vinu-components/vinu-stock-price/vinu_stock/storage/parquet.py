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


def _bars_to_table(bars: list[BarRecord]) -> pa.Table:
    if not bars:
        return pa.table({name: pa.array([], type=typ) for name, typ in _BAR_FIELDS})
    data = {
        name: pa.array([getattr(b, name) for b in bars], type=typ)
        for name, typ in _BAR_FIELDS
    }
    return pa.table(data)


def _dedupe_bars(bars: list[BarRecord]) -> list[BarRecord]:
    seen: dict[tuple[str, str, int], BarRecord] = {}
    for bar in bars:
        key = (bar.symbol, bar.provider, bar.bar_ts)
        seen[key] = bar
    return sorted(seen.values(), key=lambda b: b.bar_ts)


def _read_existing(path: Path) -> list[BarRecord]:
    if not path.is_file():
        return []
    table = pq.read_table(path)
    rows = table.to_pylist()
    return [BarRecord.from_dict(row) for row in rows]


def write_bars(path: Path, bars: list[BarRecord], *, merge: bool = True) -> int:
    """Write bars to parquet; merge+dedupe with existing file if merge=True."""
    path.parent.mkdir(parents=True, exist_ok=True)
    combined = list(bars)
    if merge and path.is_file():
        combined = _read_existing(path) + combined
    combined = _dedupe_bars(combined)
    pq.write_table(_bars_to_table(combined), path, compression="zstd")
    return len(combined)


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
        existing = _read_existing(day_path) if day_path.is_file() else []
        combined = _dedupe_bars(existing + day_bars)
        pq.write_table(_bars_to_table(combined), day_path, compression="zstd")
        total += len(combined)

    return total


def read_bars(path: Path) -> list[BarRecord]:
    """Read bars, including any daily incremental files created by append_bars."""
    all_bars: list[BarRecord] = []
    if path.is_file():
        all_bars.extend(_read_existing(path))
    stem = path.stem
    for sibling in sorted(path.parent.glob(f"{stem}_*.parquet")):
        if sibling.name != path.name:
            all_bars.extend(_read_existing(sibling))
    return _dedupe_bars(all_bars)
