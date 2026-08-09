from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.dlinear.backtest import MIN_OBSERVATIONS, run_dlinear_backtest
from vinu_initial_analysis.storage.weights import WeightsStore


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_OBSERVATIONS + 20)
    with TemporaryDirectory() as tmp:
        df = run_dlinear_backtest("AAPL", "1D", bars, tmp)
    assert len(df) == 20


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    with TemporaryDirectory() as tmp:
        df = run_dlinear_backtest("AAPL", "1D", bars, tmp)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_weights_are_saved_and_reloadable():
    bars = _make_bars(n=MIN_OBSERVATIONS + 3)
    with TemporaryDirectory() as tmp:
        df = run_dlinear_backtest("AAPL", "1D", bars, tmp)
        store = WeightsStore(tmp)
        state_dict = store.load(df.iloc[0]["weights_ref"])
    assert "linear_trend.weight" in state_dict


def test_hit_is_boolean_direction_agreement():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    with TemporaryDirectory() as tmp:
        df = run_dlinear_backtest("AAPL", "1D", bars, tmp)
    assert set(df["hit"].unique()).issubset({0, 1})


def test_too_short_history_produces_no_steps():
    bars = _make_bars(n=MIN_OBSERVATIONS - 1)
    with TemporaryDirectory() as tmp:
        df = run_dlinear_backtest("AAPL", "1D", bars, tmp)
    assert len(df) == 0
