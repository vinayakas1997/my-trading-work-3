from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_initial_analysis.storage.parquet import AngleStorage


def _storage(tmp: str) -> AngleStorage:
    return AngleStorage(data_root=tmp)


def _write_runs(storage: AngleStorage, symbol: str, angle: str, n: int, *, tier: str = "tier2") -> list[str]:
    run_ids = []
    for _ in range(n):
        df = pd.DataFrame({"foo": [1.0]})
        rid = storage.write(symbol, angle, df, tier=tier)
        run_ids.append(rid)
    return run_ids


class TestAngleStorageCleanup:
    # These tests write tier="tier3" explicitly: cleanup_max_runs pruning now
    # only ever applies to tier3 (ad-hoc/triggered) runs -- tier2 (scheduled
    # quarterly, the official record) is never pruned, see
    # test_tier2_is_never_pruned below and AngleStorage._cleanup's docstring.
    def test_cleanup_keeps_at_most_max_runs(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            run_ids = _write_runs(storage, "AAPL", "trend_lifecycle", 5, tier="tier3")
            assert len(storage._list_files("AAPL", "trend_lifecycle")) == 5

    def test_cleanup_removes_oldest_when_exceeded(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "trend_lifecycle", 15, tier="tier3")
            files = storage._list_files("AAPL", "trend_lifecycle")
            assert len(files) == 10, f"expected 10, got {len(files)}"

    def test_cleanup_disabled_with_zero(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            for _ in range(15):
                storage.write("AAPL", "test", pd.DataFrame({"x": [1.0]}), cleanup_max_runs=0, tier="tier3")
            files = storage._list_files("AAPL", "test")
            assert len(files) == 15

    def test_cleanup_keeps_most_recent(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 12, tier="tier3")
            files = storage._list_files("AAPL", "test")
            assert len(files) == 10
            # All surviving files should have run_id starting with the run_id
            # of the most recent runs (we can check read works and returns data)

    def test_tier2_is_never_pruned(self):
        """The immutability fix: tier2 (scheduled quarterly, the official
        record) must survive past cleanup_max_runs no matter how many runs
        pile up -- only tier3 is prunable. Uses the default tier ("tier2")
        and default cleanup_max_runs (10) to mirror a real angle write."""
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "trend_lifecycle", 15, tier="tier2")
            files = storage._list_files("AAPL", "trend_lifecycle")
            assert len(files) == 15


class TestAngleStorageRead:
    def test_read_after_cleanup_returns_data(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            _write_runs(storage, "AAPL", "test", 12)
            df = storage.read("AAPL", "test")
            # read() surfaces only the latest run — older runs are superseded
            # results for the same angle, not additional data points, so they
            # must not be concatenated in (that silently double-counts events
            # on every re-run).
            assert len(df) == 1

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


class TestAngleStoragePathShape:
    def test_single_ticker_path_nests_granularity_and_tier(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            run_id = storage.write(
                "AAPL", "kronos", pd.DataFrame({"x": [1.0]}),
                run_id="run_8f3a2b", granularity="1H", tier="tier3",
            )
            expected = Path(tmp) / "analysis" / "AAPL" / "kronos" / "1H" / "tier3" / f"{run_id}.parquet"
            assert expected.is_file()

    def test_different_granularities_do_not_collide(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            storage.write("AAPL", "kronos", pd.DataFrame({"x": [1.0]}), run_id="r1", granularity="1H")
            storage.write("AAPL", "kronos", pd.DataFrame({"x": [2.0]}), run_id="r2", granularity="1D")
            df_1h = storage.read("AAPL", "kronos", granularity="1H")
            df_1d = storage.read("AAPL", "kronos", granularity="1D")
            assert df_1h.iloc[0]["x"] == 1.0
            assert df_1d.iloc[0]["x"] == 2.0

    def test_multi_ticker_write_routes_under_multi_dir(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            run_id = storage.write(
                "AAPL", "cross_attention_fusion", pd.DataFrame({"x": [1.0]}),
                run_id="run_multi1", tickers=["MSFT", "aapl"],
            )
            ticker_hash = AngleStorage._ticker_hash(["MSFT", "aapl"])
            expected = (
                Path(tmp) / "analysis" / "_multi" / ticker_hash / "cross_attention_fusion"
                / "1D" / "tier2" / f"{run_id}.parquet"
            )
            assert expected.is_file()

    def test_multi_ticker_hash_is_order_and_case_insensitive(self):
        assert AngleStorage._ticker_hash(["AAPL", "MSFT"]) == AngleStorage._ticker_hash(["msft", "aapl"])

    def test_multi_ticker_read_round_trips(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            storage.write(
                "AAPL", "cross_attention_fusion", pd.DataFrame({"x": [42.0]}),
                tickers=["AAPL", "MSFT"],
            )
            df = storage.read("AAPL", "cross_attention_fusion", tickers=["MSFT", "AAPL"])
            assert df.iloc[0]["x"] == 42.0

    def test_list_symbols_excludes_multi(self):
        with TemporaryDirectory() as tmp:
            storage = _storage(tmp)
            storage.write("AAPL", "test", pd.DataFrame({"x": [1.0]}))
            storage.write("AAPL", "cross_attention_fusion", pd.DataFrame({"x": [1.0]}), tickers=["AAPL", "MSFT"])
            symbols = storage.list_symbols()
            assert symbols == ["AAPL"]
