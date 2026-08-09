from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.exponential_smoothing.backtest import (
    _direction,
    es_step,
    run_es_backtest,
)
from vinu_initial_analysis.angles.exponential_smoothing.compute import MIN_OBSERVATIONS
from vinu_initial_analysis.angles.exponential_smoothing.naive_baseline import run_naive_baseline


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_OBSERVATIONS + 15)
    df = run_es_backtest("AAPL", "1D", bars)
    assert len(df) == 15


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_es_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_hit_is_direction_match_not_ci_coverage():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_es_backtest("AAPL", "1D", bars)
    assert "confidence_interval" not in df.columns
    for _, row in df.iterrows():
        if row["status"] == "ok":
            expected_hit = int(row["predicted_direction"] == row["actual_direction"])
            assert row["hit"] == expected_hit


def test_no_weights_ref_column():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_es_backtest("AAPL", "1D", bars)
    assert "weights_ref" not in df.columns


def test_parallel_output_is_row_for_row_identical_to_sequential():
    bars = _make_bars(n=MIN_OBSERVATIONS + 20)
    sequential = run_es_backtest("AAPL", "1D", bars)
    parallel = run_es_backtest("AAPL", "1D", bars, parallel=True, chunk_size=5, n_workers=2)
    pd.testing.assert_frame_equal(
        sequential.reset_index(drop=True), parallel.reset_index(drop=True),
    )


def test_direction_helper_thresholds():
    assert _direction(0.01) == "up"
    assert _direction(-0.01) == "down"
    assert _direction(0.0) == "flat"


def test_naive_baseline_forecast_is_always_last_close():
    bars = _make_bars(n=MIN_OBSERVATIONS + 8)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert len(df) == 8
    for i, row in df.iterrows():
        history_len = MIN_OBSERVATIONS + i
        assert row["forecast"] == bars["close"].iloc[history_len - 1]
    assert "hit" not in df.columns
    assert "weights_ref" not in df.columns
