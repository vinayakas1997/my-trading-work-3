from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.chronos.backtest import HORIZON, run_chronos_backtest
from vinu_initial_analysis.angles.chronos.compute import MIN_OBSERVATIONS
from vinu_initial_analysis.angles.chronos.naive_baseline import run_naive_baseline

# Real chronos-t5-large calls are genuinely expensive (~14s each, benchmarked
# directly on this CPU-only environment) -- unlike ARIMA/DLinear's synthetic
# per-step tests, this module runs the real backtest ONCE (module-scoped
# fixture, deliberately only 2 steps) and reuses the result across several
# assertions, instead of a fresh small backtest per test.


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


@pytest.fixture(scope="module")
def small_backtest_result() -> pd.DataFrame:
    # 2 steps: min_observations + horizon + 1 = 512 + 5 + 1
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 1)
    return run_chronos_backtest("AAPL", "1D", bars)


def test_row_count_matches_formula(small_backtest_result):
    assert len(small_backtest_result) == 2


def test_rows_are_tagged_consistently_with_tag_row(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_predictions_nested_dict_has_all_five_horizon_steps(small_backtest_result):
    row0 = small_backtest_result.iloc[0]
    predictions = row0["predictions"]
    # String keys, not ints -- pyarrow/parquet rejects non-str/bytes dict
    # keys (see 03-chronos/01-implementation.md Bug 2).
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert set(step_data.keys()) == {"p10", "median", "p90", "actual", "hit"}
        assert step_data["hit"] in (0, 1)


def test_hit_matches_band_membership(small_backtest_result):
    for _, row in small_backtest_result.iterrows():
        for step_data in row["predictions"].values():
            expected_hit = int(step_data["p10"] <= step_data["actual"] <= step_data["p90"])
            assert step_data["hit"] == expected_hit


def test_no_weights_ref_column(small_backtest_result):
    assert "weights_ref" not in small_backtest_result.columns


def test_naive_baseline_predictions_shape():
    bars = _make_bars(n=MIN_OBSERVATIONS + HORIZON + 1)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert len(df) == 2
    row0 = df.iloc[0]
    predictions = row0["predictions"]
    assert set(predictions.keys()) == {"1", "2", "3", "4", "5"}
    for step_data in predictions.values():
        assert "hit" not in step_data  # naive has no meaningful band-coverage metric
        assert step_data["squared_error"] == (step_data["actual"] - step_data["forecast"]) ** 2
    assert "weights_ref" not in df.columns
