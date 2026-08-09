from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from vinu_initial_analysis.storage.factsheet import generate_factsheet
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.orchestration import AngleRunStatus
from vinu_initial_analysis.storage.orchestration_registry import run_batch_with_parallel_harness
from vinu_initial_analysis.storage.parquet import AngleStorage


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_run_log_opt_in_persists_and_writes_a_real_fact_sheet_after_the_batch():
    # This is the behavior the whole point of this pass depended on: before
    # this, run_batch_with_parallel_harness only ever returned DataFrames in
    # memory -- nothing landed in AngleStorage/RunLog, so there was nothing
    # for a fact sheet to read. Passing run_log= makes the file "there"
    # right after the batch, for real.
    bars_by_symbol = {"AAPL": _make_bars(130)}
    with TemporaryDirectory() as tmp:
        tracker = AngleRunStatus(Path(tmp) / "tracker.db")
        run_log = RunLog(Path(tmp) / "runs.db")
        storage = AngleStorage(tmp, run_log=run_log)
        try:
            summary = run_batch_with_parallel_harness(
                tracker, "persist-test", ["AAPL"], bars_by_symbol, tmp,
                angle_names=["arima", "kalman_filters"],
                n_workers=2, chunk_size=20, min_total_steps_for_parallel=0,
                run_log=run_log,
            )
            assert summary["ok"]

            # Real RunLog + AngleStorage round-trip, not just an in-memory result.
            run = run_log.get_latest_run("AAPL", "arima", granularity="1D", tier="tier2")
            assert run is not None
            assert run["row_count"] > 0
            stored = storage.read_latest("AAPL", "arima", granularity="1D", tier="tier2")
            assert len(stored) == run["row_count"]

            # Real analysis_from/analysis_until, derived from this run's own
            # real step bar_ts min/max (not the raw input bars -- ARIMA's
            # own min_observations means its first real step starts later
            # than the input bars' own earliest bar_ts). These columns
            # existed in the schema before this but were never populated by
            # this batch path (confirmed: always NaT).
            assert stored["analysis_from"].notna().all()
            assert stored["analysis_until"].notna().all()
            assert stored["analysis_from"].iloc[0] == pd.Timestamp(stored["bar_ts"].min(), unit="s", tz="UTC")
            assert stored["analysis_until"].iloc[0] == pd.Timestamp(stored["bar_ts"].max(), unit="s", tz="UTC")

            # Real fact sheet file on disk, matching what generate_factsheet
            # would produce directly from the same real stored data.
            factsheet_path = Path(tmp) / "factsheets" / "AAPL" / "arima.md"
            assert factsheet_path.is_file()
            expected = generate_factsheet("AAPL", "arima", run_log, storage)
            assert factsheet_path.read_text(encoding="utf-8") == expected

            kalman_path = Path(tmp) / "factsheets" / "AAPL" / "kalman_filters.md"
            assert kalman_path.is_file()

            summary_path = Path(tmp) / "factsheets" / "AAPL" / "_summary.md"
            assert summary_path.is_file()
            summary_text = summary_path.read_text(encoding="utf-8")
            assert "arima" in summary_text
            assert "kalman_filters" in summary_text
        finally:
            tracker.close()
            run_log.close()


def test_without_run_log_nothing_is_written_to_disk_unchanged_behavior():
    bars_by_symbol = {"AAPL": _make_bars(130)}
    with TemporaryDirectory() as tmp:
        tracker = AngleRunStatus(Path(tmp) / "tracker.db")
        try:
            summary = run_batch_with_parallel_harness(
                tracker, "no-persist-test", ["AAPL"], bars_by_symbol, tmp,
                angle_names=["arima"], n_workers=2, chunk_size=20,
                min_total_steps_for_parallel=0,
            )
            assert summary["ok"]
            assert not (Path(tmp) / "factsheets").exists()
            assert not (Path(tmp) / "analysis").exists()
        finally:
            tracker.close()
