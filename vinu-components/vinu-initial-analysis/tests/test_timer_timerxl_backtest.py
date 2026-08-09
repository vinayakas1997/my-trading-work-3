from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.timer_timerxl.backtest import HORIZON, run_timer_timerxl_backtest
from vinu_initial_analysis.angles.timer_timerxl.compute import MIN_OBSERVATIONS
from vinu_initial_analysis.angles.timer_timerxl.naive_baseline import run_naive_baseline

# Real Timer calls are cheap once the model is cached in-process (~0.01s
# warm, benchmarked directly -- unlike Chronos-t5-large's ~14s/call), so
# this module runs a real, several-step backtest rather than a single
# minimal one.


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


@pytest.fixture(scope="module")
def small_backtest_result() -> pd.DataFrame:
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 4)
    return run_timer_timerxl_backtest("AAPL", "1D", bars)


def test_row_count_matches_formula(small_backtest_result):
    assert len(small_backtest_result) == 5


def test_rows_are_tagged_consistently_with_tag_row(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_predictions_nested_dict_has_all_five_horizon_steps(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert set(step_data.keys()) == {"point", "p10", "p90", "actual", "hit", "in_band", "close_sq_error", "close_abs_error"}
        assert step_data["hit"] in (0, 1)
        assert step_data["in_band"] in (0, 1)


def test_in_band_matches_band_membership(small_backtest_result):
    for _, row in small_backtest_result.iterrows():
        for step_data in row["predictions"].values():
            expected = int(step_data["p10"] <= step_data["actual"] <= step_data["p90"])
            assert step_data["in_band"] == expected
            assert step_data["close_sq_error"] == (step_data["actual"] - step_data["point"]) ** 2


def test_no_weights_ref_column(small_backtest_result):
    assert "weights_ref" not in small_backtest_result.columns


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
