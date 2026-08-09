from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles.regime_analysis.backtest import (
    run_per_bar_regime_backtest,
    run_quarterly_regime_breakdown,
)
from vinu_initial_analysis.angles.regime_analysis.compute import MIN_OBSERVATIONS, classify_regime, compute


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1.0, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_classify_regime_high_vol_takes_priority():
    assert classify_regime(ret_20d=0.05, vol_z=1.5) == "high_vol"


def test_classify_regime_bull_bear_sideways():
    assert classify_regime(ret_20d=0.02, vol_z=0.0) == "bull"
    assert classify_regime(ret_20d=-0.02, vol_z=0.0) == "bear"
    assert classify_regime(ret_20d=0.0, vol_z=0.0) == "sideways"


def test_compute_insufficient_data_below_floor():
    bars = _make_bars(n=MIN_OBSERVATIONS - 1)
    df = compute("AAPL", bars=bars)
    assert df.iloc[0]["status"] == "insufficient_data"


def test_compute_transition_rows_have_normalized_probability():
    bars = _make_bars(n=MIN_OBSERVATIONS + 100)
    df = compute("AAPL", bars=bars)
    transitions = df[df["metric"] == "transition"]
    assert not transitions.empty
    for _, row in transitions.iterrows():
        assert 0.0 <= row["transition_prob"] <= 1.0
        assert row["transition_prob"] == round(row["count"] / row["n_from_regime"], 6)


def test_per_bar_backtest_produces_date_only_tagged_rows():
    bars = _make_bars(n=MIN_OBSERVATIONS + 50)
    df = run_per_bar_regime_backtest("AAPL", bars)
    assert not df.empty
    assert "session" not in df.columns
    for col in ("day_of_week", "week_of_month", "month", "quarter", "regime", "ret_20d", "vol_21d", "vol_trailing_z"):
        assert col in df.columns
    assert set(df["regime"].unique()) <= {"bull", "bear", "high_vol", "sideways"}


def test_per_bar_backtest_empty_below_floor():
    bars = _make_bars(n=MIN_OBSERVATIONS - 1)
    df = run_per_bar_regime_backtest("AAPL", bars)
    assert df.empty


def test_quarterly_breakdown_percentages_sum_to_one_per_quarter():
    bars = _make_bars(n=MIN_OBSERVATIONS + 200)
    df = run_quarterly_regime_breakdown("AAPL", bars)
    assert not df.empty
    for quarter, group in df.groupby("quarter_key"):
        assert group["pct_of_time_in_quarter"].sum() == pytest.approx(1.0, abs=1e-9)
