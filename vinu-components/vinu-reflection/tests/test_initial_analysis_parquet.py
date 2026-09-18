"""Tests for the torch-free vinu-initial-analysis Parquet reader behind
analyses Q and N. See
vinu_reflection/reflection/_initial_analysis_parquet.py's own docstring.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from vinu_reflection.reflection._initial_analysis_parquet import (
    list_analyzed_symbols,
    read_all_runs,
    read_latest_run,
)


def _write_run(
    data_root: Path, symbol: str, angle_name: str, rows: list[dict],
    *, granularity: str = "1D", tier: str = "tier2", run_id: str,
) -> None:
    base = data_root / "analysis" / symbol / angle_name / granularity / tier
    base.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df["stored_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
    df.to_parquet(base / f"{run_id}.parquet", index=False)


class TestListAnalyzedSymbols:
    def test_no_data_returns_empty(self, tmp_path):
        assert list_analyzed_symbols(tmp_path) == []

    def test_lists_symbols_excluding_multi(self, tmp_path):
        _write_run(tmp_path, "AAPL", "lstm", [{"hit": 1}], run_id="r1")
        _write_run(tmp_path, "MSFT", "lstm", [{"hit": 0}], run_id="r2")
        (tmp_path / "analysis" / "_multi").mkdir(parents=True, exist_ok=True)

        assert list_analyzed_symbols(tmp_path) == ["AAPL", "MSFT"]


class TestReadLatestRun:
    def test_no_data_returns_empty_dataframe(self, tmp_path):
        df = read_latest_run(tmp_path, "AAPL", "lstm")
        assert df.empty

    def test_reads_the_newest_run_by_mtime(self, tmp_path):
        _write_run(tmp_path, "AAPL", "lstm", [{"hit": 0, "bar_ts": 1}], run_id="old")
        time.sleep(0.05)
        _write_run(tmp_path, "AAPL", "lstm", [{"hit": 1, "bar_ts": 2}, {"hit": 1, "bar_ts": 3}], run_id="new")

        df = read_latest_run(tmp_path, "AAPL", "lstm")
        assert len(df) == 2
        assert df["bar_ts"].tolist() == [2, 3]

    def test_malformed_file_returns_empty_not_raises(self, tmp_path):
        base = tmp_path / "analysis" / "AAPL" / "lstm" / "1D" / "tier2"
        base.mkdir(parents=True, exist_ok=True)
        (base / "broken.parquet").write_text("not a real parquet file")

        df = read_latest_run(tmp_path, "AAPL", "lstm")
        assert df.empty


class TestReadAllRuns:
    def test_no_data_returns_empty_dataframe(self, tmp_path):
        df = read_all_runs(tmp_path, "AAPL", "shock_personality")
        assert df.empty

    def test_concatenates_every_run_sorted_by_stored_at(self, tmp_path):
        _write_run(tmp_path, "AAPL", "shock_personality", [{"n_shocks": 1}], run_id="q1")
        time.sleep(0.05)
        _write_run(tmp_path, "AAPL", "shock_personality", [{"n_shocks": 2}], run_id="q2")
        time.sleep(0.05)
        _write_run(tmp_path, "AAPL", "shock_personality", [{"n_shocks": 3}], run_id="q3")

        df = read_all_runs(tmp_path, "AAPL", "shock_personality")
        assert df["n_shocks"].tolist() == [1, 2, 3]
