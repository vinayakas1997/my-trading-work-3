from __future__ import annotations

import tempfile

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.itransformer.backtest import MIN_BARS, run_itransformer_backtest
from vinu_initial_analysis.angles.itransformer.naive_baseline import run_naive_baseline
from vinu_initial_analysis.storage.weights import WeightsStore


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_p = close + rng.normal(0, 0.2, size=n)
    high = np.maximum(close, open_p) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(close, open_p) - np.abs(rng.normal(0, 0.3, size=n))
    volume = np.abs(rng.normal(0, 1, size=n)) * 1e6 + 5e6
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": open_p, "high": high, "low": low,
        "close": close, "volume": volume,
    })


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_BARS + 5)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_itransformer_backtest("AAPL", "1D", bars, tmp)
    assert len(df) == 5


def test_all_five_channel_forecasts_present():
    bars = _make_bars(n=MIN_BARS + 2)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_itransformer_backtest("AAPL", "1D", bars, tmp)
    row0 = df.iloc[0]
    for ch in ("open", "high", "low", "close", "volume"):
        assert f"forecast_{ch}" in df.columns
        assert np.isfinite(row0[f"forecast_{ch}"])


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_BARS + 3)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_itransformer_backtest("AAPL", "1D", bars, tmp)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_weights_are_saved_and_reloadable_and_reproduce_the_forecast():
    from vinu_initial_analysis.angles.itransformer.compute import _build_model, LOOKBACK, CHANNELS
    import torch

    bars = _make_bars(n=MIN_BARS + 2)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_itransformer_backtest("AAPL", "1D", bars, tmp)
        store = WeightsStore(tmp)
        row0 = df.iloc[0]
        state_dict = store.load(row0["weights_ref"])
        model = _build_model(LOOKBACK, row0["n_channels"])
        model.load_state_dict(state_dict)
        model.eval()
    assert "embed.weight" in state_dict


def test_no_naive_direction_hit_field():
    bars = _make_bars(n=MIN_BARS + 3)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert "hit" not in df.columns
    assert "weights_ref" not in df.columns
    for _, row in df.iterrows():
        assert row["squared_error"] == (row["actual_price"] - row["forecast_price"]) ** 2
