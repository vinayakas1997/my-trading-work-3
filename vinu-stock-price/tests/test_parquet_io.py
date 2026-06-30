"""Parquet IO tests."""

from __future__ import annotations

from pathlib import Path

from vinu_stock.storage.models import BarRecord
from vinu_stock.storage import parquet


def test_write_and_read_dedupe(tmp_path: Path) -> None:
    path = tmp_path / "test.parquet"
    bars = [
        BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.5, 100),
        BarRecord("AAPL", "test", 1060, 1.5, 2.5, 1.0, 2.0, 200),
    ]
    parquet.write_bars(path, bars)
    assert len(parquet.read_bars(path)) == 2

    overlap = [
        BarRecord("AAPL", "test", 1000, 1, 2, 0.5, 1.6, 150),
        BarRecord("AAPL", "test", 1120, 2.0, 3.0, 1.5, 2.5, 50),
    ]
    parquet.append_bars(path, overlap)
    read = parquet.read_bars(path)
    assert len(read) == 3
    by_ts = {b.bar_ts: b for b in read}
    assert by_ts[1000].close == 1.6
