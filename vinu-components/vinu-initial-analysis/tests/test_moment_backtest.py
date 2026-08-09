from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.moment.backtest import HORIZON, run_moment_backtest
from vinu_initial_analysis.angles.moment.compute import MIN_OBSERVATIONS
from vinu_initial_analysis.angles.moment.naive_baseline import run_naive_baseline


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations_and_horizon():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 5)
    df = run_moment_backtest("AAPL", "1D", bars)
    assert len(df) == 6


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 3)
    df = run_moment_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_predictions_nested_dict_has_all_five_horizon_steps_and_two_quantiles():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 3)
    df = run_moment_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert set(step_data.keys()) == {
            "point", "p10", "p90", "actual_close", "hit",
            "pinball_loss", "close_sq_error", "close_abs_error",
        }
        assert step_data["hit"] in (0, 1)
        assert set(step_data["pinball_loss"].keys()) == {"0.1", "0.9"}


def test_hit_matches_band_membership_and_errors_are_consistent():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 5)
    df = run_moment_backtest("AAPL", "1D", bars)
    for _, row in df.iterrows():
        for step_data in row["predictions"].values():
            expected_hit = int(step_data["p10"] <= step_data["actual_close"] <= step_data["p90"])
            assert step_data["hit"] == expected_hit
            assert step_data["close_sq_error"] == (step_data["actual_close"] - step_data["point"]) ** 2
            assert step_data["close_abs_error"] == abs(step_data["actual_close"] - step_data["point"])


def test_no_weights_ref_column():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 2)
    df = run_moment_backtest("AAPL", "1D", bars)
    assert "weights_ref" not in df.columns


def test_naive_baseline_predictions_shape():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 3)
    df = run_naive_baseline("AAPL", "1D", bars)
    row0 = df.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert "hit" not in step_data
        assert step_data["close_sq_error"] == (step_data["actual"] - step_data["forecast"]) ** 2
    assert "weights_ref" not in df.columns
