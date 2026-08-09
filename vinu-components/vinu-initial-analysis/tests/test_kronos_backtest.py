from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kronos.backtest import HORIZON, WALK_FORWARD_MIN_OBSERVATIONS, run_kronos_backtest
from vinu_initial_analysis.angles.kronos.naive_baseline import run_naive_baseline

# Real Kronos-base calls are genuinely expensive (~5s each, benchmarked
# directly) -- this module runs the real backtest ONCE (module-scoped
# fixture, deliberately only 2 steps) and reuses the result across
# several assertions, same approach as test_chronos_backtest.py.


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_p = close + rng.normal(0, 0.2, size=n)
    high = np.maximum(close, open_p) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(close, open_p) - np.abs(rng.normal(0, 0.3, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": open_p, "high": high, "low": low, "close": close,
    })


@pytest.fixture(scope="module")
def small_backtest_result() -> pd.DataFrame:
    bars = _make_bars(n=WALK_FORWARD_MIN_OBSERVATIONS + HORIZON + 1)  # 2 steps
    return run_kronos_backtest("AAPL", "1D", bars)


def test_row_count_matches_formula(small_backtest_result):
    assert len(small_backtest_result) == 2


def test_rows_are_tagged_consistently_with_tag_row(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_predictions_nested_dict_uses_string_keys_and_has_full_ohlc(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert set(step_data.keys()) == {
            "open", "high", "low", "close", "actual_close",
            "predicted_direction", "actual_direction", "hit", "close_sq_error",
        }
        assert step_data["hit"] in (0, 1)
        assert step_data["close_sq_error"] >= 0


def test_close_sq_error_matches_the_real_formula(small_backtest_result):
    for _, row in small_backtest_result.iterrows():
        for step_data in row["predictions"].values():
            expected = (step_data["actual_close"] - step_data["close"]) ** 2
            assert abs(step_data["close_sq_error"] - expected) < 1e-9


def test_no_weights_ref_column(small_backtest_result):
    assert "weights_ref" not in small_backtest_result.columns


def test_naive_baseline_predictions_shape():
    bars = _make_bars(n=WALK_FORWARD_MIN_OBSERVATIONS + HORIZON + 1)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert len(df) == 2
    row0 = df.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert "hit" not in step_data
    assert "weights_ref" not in df.columns
