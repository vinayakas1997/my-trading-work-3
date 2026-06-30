"""Parquet read/write for 1m OHLCV bars."""

from __future__ import annotations

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
]


def _bars_to_table(bars: list[BarRecord]) -> pa.Table:
    if not bars:
        return pa.table({name: pa.array([], type=typ) for name, typ in _BAR_FIELDS})
    data = {name: [] for name, _ in _BAR_FIELDS}
    for bar in bars:
        row = bar.to_dict()
        for name, _ in _BAR_FIELDS:
            data[name].append(row[name])
    return pa.table({name: pa.array(data[name], type=typ) for name, typ in _BAR_FIELDS})


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
    return write_bars(path, bars, merge=True)


def read_bars(path: Path) -> list[BarRecord]:
    return _read_existing(path)
