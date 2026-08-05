import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.dlinear.compute import compute


def _make_bars(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(rng.randn(n) * 0.5)
    open_p = close + rng.randn(n) * 0.2
    high = np.maximum(close, open_p) + np.abs(rng.randn(n) * 0.3)
    low = np.minimum(close, open_p) - np.abs(rng.randn(n) * 0.3)
    volume = np.abs(rng.randn(n) * 1000 + 5000)
    return pd.DataFrame(
        {"open": open_p, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def test_no_data_returns_status_no_data():
    df = compute("AAPL", bars=None)
    row = df.iloc[0]
    assert row["status"] == "no_data"
    assert row["symbol"] == "AAPL"
    assert row["angle"] == "dlinear"


def test_insufficient_data_status():
    # Below MIN_BARS=80 — not enough history to build meaningful sliding
    # training windows for even this tiny linear model.
    df = compute("AAPL", bars=_make_bars(n=30))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fits_and_forecasts_finite_point_value():
    df = compute("AAPL", bars=_make_bars(n=200))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert np.isfinite(row["forecast_price"])
    assert np.isfinite(row["forecast_return"])
    assert row["direction"] in ("up", "down", "flat")
    assert row["n_train_windows"] > 0
    assert np.isfinite(row["train_loss"])


def test_deterministic_with_fixed_seed():
    bars = _make_bars(n=200)
    df1 = compute("AAPL", bars=bars, seed=7)
    df2 = compute("AAPL", bars=bars, seed=7)
    assert df1.iloc[0]["forecast_price"] == df2.iloc[0]["forecast_price"]
    assert df1.iloc[0]["forecast_return"] == df2.iloc[0]["forecast_return"]
