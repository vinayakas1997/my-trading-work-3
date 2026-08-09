from __future__ import annotations

import tempfile

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.tft.backtest import run_tft_backtest
from vinu_initial_analysis.angles.tft.compute import MIN_BARS
from vinu_initial_analysis.angles.tft.naive_baseline import run_naive_baseline
from vinu_initial_analysis.storage.weights import WeightsStore


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close + np.abs(rng.normal(0, 0.3, size=n))
    low = close - np.abs(rng.normal(0, 0.3, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "high": high, "low": low, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_BARS + 8)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_tft_backtest("AAPL", "1D", bars, tmp)
    assert len(df) == 8


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_BARS + 3)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_tft_backtest("AAPL", "1D", bars, tmp)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_quantiles_ordered_and_hit_in_band_fields_consistent():
    bars = _make_bars(n=MIN_BARS + 10)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_tft_backtest("AAPL", "1D", bars, tmp)
    for _, row in df.iterrows():
        assert row["forecast_price_p10"] <= row["forecast_price_p50"] <= row["forecast_price_p90"]
        assert row["hit"] in (0, 1)
        assert row["in_band"] in (0, 1)
        expected_in_band = int(row["forecast_price_p10"] <= row["actual_price"] <= row["forecast_price_p90"])
        assert row["in_band"] == expected_in_band
        assert set(row["pinball_loss"].keys()) == {"0.1", "0.5", "0.9"}
        assert row["close_sq_error"] == (row["actual_price"] - row["forecast_price_p50"]) ** 2


def test_weights_are_saved_and_reloadable():
    bars = _make_bars(n=MIN_BARS + 2)
    with tempfile.TemporaryDirectory() as tmp:
        df = run_tft_backtest("AAPL", "1D", bars, tmp)
        store = WeightsStore(tmp)
        row0 = df.iloc[0]
        state_dict = store.load(row0["weights_ref"])
    assert any("lstm" in k for k in state_dict)
    assert any("var_select" in k for k in state_dict)


def test_naive_baseline_has_no_hit_or_weights_columns():
    bars = _make_bars(n=MIN_BARS + 3)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert "hit" not in df.columns
    assert "weights_ref" not in df.columns
    for _, row in df.iterrows():
        assert row["close_sq_error"] == (row["actual_price"] - row["forecast_price"]) ** 2
