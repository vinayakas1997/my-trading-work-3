from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.timesfm.backtest import HORIZON, run_timesfm_backtest
from vinu_initial_analysis.angles.timesfm.compute import DECILE_LEVELS, MIN_OBSERVATIONS
from vinu_initial_analysis.angles.timesfm.naive_baseline import run_naive_baseline

# Real TimesFM calls are cheap once the model is cached in-process
# (~0.15s warm, benchmarked directly), so this module runs a real,
# several-step backtest.


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


@pytest.fixture(scope="module")
def small_backtest_result() -> pd.DataFrame:
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 4)
    return run_timesfm_backtest("AAPL", "1D", bars)


def test_row_count_matches_formula(small_backtest_result):
    assert len(small_backtest_result) == 5


def test_rows_are_tagged_consistently_with_tag_row(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_predictions_nested_dict_has_all_five_horizon_steps_and_nine_deciles(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    expected_decile_keys = {f"q{int(q * 100)}" for q in DECILE_LEVELS}
    for step_data in predictions.values():
        assert expected_decile_keys <= set(step_data.keys())
        assert step_data["hit"] in (0, 1)
        assert set(step_data["pinball_loss"].keys()) == {str(q) for q in DECILE_LEVELS}


def test_hit_matches_band_membership_and_errors_are_consistent(small_backtest_result):
    for _, row in small_backtest_result.iterrows():
        for step_data in row["predictions"].values():
            expected_hit = int(step_data["q10"] <= step_data["actual_close"] <= step_data["q90"])
            assert step_data["hit"] == expected_hit
            assert step_data["close_sq_error"] == (step_data["actual_close"] - step_data["q50"]) ** 2


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
