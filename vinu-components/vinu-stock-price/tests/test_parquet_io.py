"""Parquet IO tests."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from vinu_stock.storage.models import BarRecord
from vinu_stock.storage import parquet


def test_writes_never_leave_a_partial_file_at_the_target_path(tmp_path: Path, monkeypatch) -> None:
    # Regression test for known-issues.md #2: a crash mid-write must never
    # leave a truncated file at the real target path (the failure mode
    # that corrupted two real live-ingest shard files).
    path = tmp_path / "test.parquet"
    bars = [BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.5, 100)]
    parquet.write_bars(path, parquet.bars_to_table(bars))
    assert path.is_file()
    good_size = path.stat().st_size

    def _boom(*args, **kwargs):
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(pq, "write_table", _boom)
    more_bars = [BarRecord("AAPL", "test", 1060, 1, 2, 0.5, 1.5, 100)]
    try:
        parquet.write_bars(path, parquet.bars_to_table(more_bars))
    except OSError:
        pass

    # the original, complete file must still be intact -- not truncated,
    # not replaced by a partial write, and no leftover .tmp file.
    assert path.stat().st_size == good_size
    assert list(tmp_path.glob("*.tmp")) == []
    assert len(parquet.read_bars(path)) == 1


def test_append_bars_atomic_write_leaves_no_tmp_file(tmp_path: Path) -> None:
    path = tmp_path / "AAPL.parquet"
    bars = [BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.5, 100)]
    parquet.append_bars(path, bars)
    day_files = list(tmp_path.glob("AAPL_*.parquet"))
    assert len(day_files) == 1
    assert list(tmp_path.glob("*.tmp")) == []
    # the written file is a real, complete, readable parquet file
    pq.ParquetFile(day_files[0])


def test_write_and_read_dedupe(tmp_path: Path) -> None:
    path = tmp_path / "test.parquet"
    bars = [
        BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.5, 100),
        BarRecord("AAPL", "test", 1060, 1.5, 2.5, 1.0, 2.0, 200),
    ]
    parquet.write_bars(path, parquet.bars_to_table(bars))
    assert len(parquet.read_bars(path)) == 2

    overlap = [
        BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.6, 150),
        BarRecord("AAPL", "test", 1120, 2.0, 3.0, 1.5, 2.5, 50),
    ]
    parquet.append_bars(path, overlap)
    read = parquet.read_bars(path)
    assert len(read) == 3
    rows = read.to_pylist()
    by_ts = {r["bar_ts"]: r for r in rows}
    assert by_ts[1000]["close"] == 1.6
