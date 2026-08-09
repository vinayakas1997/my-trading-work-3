from __future__ import annotations

import tempfile

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.lstm.backtest import run_lstm_backtest
from vinu_initial_analysis.angles.lstm.compute import MIN_BARS
from vinu_initial_analysis.angles.lstm.naive_baseline import run_naive_baseline
from vinu_initial_analysis.storage.weights import WeightsStore


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_BARS + 8)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_lstm_backtest("AAPL", "1D", bars, tmp)
    assert len(df) == 8


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_BARS + 3)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_lstm_backtest("AAPL", "1D", bars, tmp)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_hit_and_rmse_fields_present_and_consistent():
    bars = _make_bars(n=MIN_BARS + 10)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_lstm_backtest("AAPL", "1D", bars, tmp)
    for _, row in df.iterrows():
        assert row["hit"] in (0, 1)
        assert row["close_sq_error"] == (row["actual_price"] - row["forecast_price"]) ** 2
        assert row["close_abs_error"] == abs(row["actual_price"] - row["forecast_price"])


def test_weights_are_saved_and_reloadable():
    bars = _make_bars(n=MIN_BARS + 2)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_lstm_backtest("AAPL", "1D", bars, tmp)
        store = WeightsStore(tmp)
        row0 = df.iloc[0]
        state_dict = store.load(row0["weights_ref"])
    assert "lstm.weight_ih_l0" in state_dict


def test_naive_baseline_has_no_hit_or_weights_columns():
    bars = _make_bars(n=MIN_BARS + 3)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert "hit" not in df.columns
    assert "weights_ref" not in df.columns
    for _, row in df.iterrows():
        assert row["close_sq_error"] == (row["actual_price"] - row["forecast_price"]) ** 2
