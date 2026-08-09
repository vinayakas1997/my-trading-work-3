"""Tests for query engine resilience to corrupt parquet files.

Regression coverage for known-issues.md #2: a single truncated/corrupt
parquet file used to fail fetch_candles() for the *entire* symbol,
regardless of the queried date range. This confirms one bad file is now
skipped (with a warning) instead of taking down the whole symbol.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from vinu_stock.query import engine
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage import parquet


def _write_symbol_layout(root: Path, symbol: str) -> Path:
    base = root / "prices" / "1m" / symbol
    (base / "archive").mkdir(parents=True)
    (base / "live").mkdir(parents=True)
    return base


def test_fetch_candles_skips_one_corrupt_live_file(tmp_path: Path) -> None:
    engine.invalidate_symbol_cache()
    base = _write_symbol_layout(tmp_path, "AAPL")

    good_bars = [BarRecord("AAPL", "test", 1000 + i * 60, 1, 2, 0.5, 1.5, 100) for i in range(3)]
    parquet.write_bars(base / "archive" / "2022.parquet", parquet.bars_to_table(good_bars))

    # a second, real live file with valid data
    live_bars = [BarRecord("AAPL", "test", 5000 + i * 60, 1, 2, 0.5, 1.5, 100) for i in range(2)]
    parquet.append_bars(base / "live" / "AAPL", live_bars)

    # a truncated/corrupt live file, same failure signature as the real
    # incident this test guards against
    corrupt = base / "live" / "AAPL_corrupt.parquet"
    corrupt.write_bytes(b"not a real parquet file")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = engine.fetch_candles(tmp_path, "AAPL", interval="1m")

    assert len(result) == 5  # the good archive + live rows, corrupt file skipped
    assert any("unreadable parquet" in str(w.message) for w in caught)


def test_fetch_candles_returns_empty_not_raises_when_all_files_corrupt(tmp_path: Path) -> None:
    engine.invalidate_symbol_cache()
    base = _write_symbol_layout(tmp_path, "JNJ")
    (base / "live" / "JNJ_corrupt.parquet").write_bytes(b"not a real parquet file")

    result = engine.fetch_candles(tmp_path, "JNJ", interval="1m")
    assert result == []
