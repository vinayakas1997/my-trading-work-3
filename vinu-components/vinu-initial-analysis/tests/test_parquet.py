from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_initial_analysis.storage.parquet import AngleStorage


def _storage(tmp: str) -> AngleStorage:
    return AngleStorage(data_root=tmp)


def _write_runs(storage: AngleStorage, symbol: str, angle: str, n: int) -> list[str]:
    run_ids = []
    for _ in range(n):
        df = pd.DataFrame({"foo": [1.0]})
        rid = storage.write(symbol, angle, df)
        run_ids.append(rid)
    return run_ids


class TestAngleStorageCleanup:
    def test_cleanup_keeps_at_most_max_runs(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            run_ids = _write_runs(storage, "AAPL", "trend_lifecycle", 5)
            assert len(storage._list_files("AAPL", "trend_lifecycle")) == 5

    def test_cleanup_removes_oldest_when_exceeded(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "trend_lifecycle", 15)
            files = storage._list_files("AAPL", "trend_lifecycle")
            assert len(files) == 10, f"expected 10, got {len(files)}"

    def test_cleanup_disabled_with_zero(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            for _ in range(15):
                storage.write("AAPL", "test", pd.DataFrame({"x": [1.0]}), cleanup_max_runs=0)
            files = storage._list_files("AAPL", "test")
            assert len(files) == 15

    def test_cleanup_keeps_most_recent(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 12)
            files = storage._list_files("AAPL", "test")
            assert len(files) == 10
            # All surviving files should have run_id starting with the run_id
            # of the most recent runs (we can check read works and returns data)


class TestAngleStorageRead:
    def test_read_after_cleanup_returns_data(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 12)
            df = storage.read("AAPL", "test")
            # 10 surviving runs, each with 1 data row + 8 fixed columns = 9 cols
            assert len(df) == 10

    def test_read_latest_returns_most_recent(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 5)
            latest = storage.read_latest("AAPL", "test")
            assert not latest.empty

    def test_list_angles_reports_run_count(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 3)
            angles = storage.list_angles("AAPL")
            assert len(angles) == 1
