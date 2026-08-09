from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.garch.backtest import _qlike, _vol_direction, run_garch_backtest
from vinu_initial_analysis.angles.garch.compute import MIN_OBSERVATIONS


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_qlike_is_zero_at_a_perfect_forecast():
    assert abs(_qlike(0.0004, 0.0004)) < 1e-9


def test_qlike_is_nonnegative_and_penalizes_error():
    close_forecast = _qlike(0.0004, 0.00041)
    far_forecast = _qlike(0.0004, 0.001)
    assert close_forecast >= 0
    assert far_forecast >= 0
    assert far_forecast > close_forecast


def test_vol_direction_thresholds():
    assert _vol_direction(0.02, 0.01) == "rising"
    assert _vol_direction(0.01, 0.02) == "falling"
    assert _vol_direction(0.01, 0.01) == "flat"


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_OBSERVATIONS + 15)
    df = run_garch_backtest("AAPL", "1D", bars)
    assert len(df) == 15


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_garch_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_qlike_and_vol_direction_hit_match_the_real_formulas():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_garch_backtest("AAPL", "1D", bars)
    for _, row in df.iterrows():
        if row["status"] != "ok":
            continue
        expected_qlike = _qlike(row["realized_variance"], row["next_period_variance_forecast"])
        assert abs(row["qlike_error"] - expected_qlike) < 1e-9
        assert row["qlike_error"] >= 0
        assert row["vol_direction_hit"] == int(row["forecasted_vol_direction"] == row["actual_vol_direction"])


def test_no_weights_ref_and_no_naive_baseline_module():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_garch_backtest("AAPL", "1D", bars)
    assert "weights_ref" not in df.columns
    import importlib
    import pytest
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("vinu_initial_analysis.angles.garch.naive_baseline")
