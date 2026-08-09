from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kalman_filters.backtest import (
    _direction,
    run_kalman_backtest,
    run_smoothed_diagnostic,
)
from vinu_initial_analysis.angles.kalman_filters.compute import MIN_OBSERVATIONS
from vinu_initial_analysis.angles.kalman_filters.naive_baseline import run_naive_baseline


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_OBSERVATIONS + 15)
    df = run_kalman_backtest("AAPL", "1D", bars)
    assert len(df) == 15


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_kalman_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_backtest_rows_never_contain_smoothed_fields():
    # The correctness-critical property: smoothed_state (non-causal) must
    # never leak into the walk-forward backtest's output.
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_kalman_backtest("AAPL", "1D", bars)
    assert "smoothed_level" not in df.columns
    assert "smoothed_trend" not in df.columns


def test_hit_matches_filtered_trend_direction():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_kalman_backtest("AAPL", "1D", bars)
    for _, row in df.iterrows():
        if row["status"] != "ok":
            continue
        expected_direction = _direction(row["filtered_trend"])
        assert row["predicted_direction"] == expected_direction
        assert row["hit"] == int(expected_direction == row["actual_direction"])


def test_no_weights_ref_column():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_kalman_backtest("AAPL", "1D", bars)
    assert "weights_ref" not in df.columns


def test_smoothed_diagnostic_is_one_row_and_untagged():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_smoothed_diagnostic("AAPL", "1D", bars)
    assert len(df) == 1
    assert "session" not in df.columns
    assert "bar_ts" not in df.columns
    assert "smoothed_level" in df.columns
    assert "smoothed_trend" in df.columns


def test_parallel_output_is_row_for_row_identical_to_sequential():
    bars = _make_bars(n=MIN_OBSERVATIONS + 20)
    sequential = run_kalman_backtest("AAPL", "1D", bars)
    parallel = run_kalman_backtest("AAPL", "1D", bars, parallel=True, chunk_size=5, n_workers=2)
    pd.testing.assert_frame_equal(
        sequential.reset_index(drop=True), parallel.reset_index(drop=True),
    )


def test_naive_baseline_is_persistence_not_flat():
    bars = _make_bars(n=MIN_OBSERVATIONS + 8)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert len(df) == 8
    # Persistence: at least some predictions should be "up" or "down",
    # not universally "flat" the way a naive-forecast-based direction
    # would trivially be.
    assert set(df["predicted_direction"].unique()) & {"up", "down"}
