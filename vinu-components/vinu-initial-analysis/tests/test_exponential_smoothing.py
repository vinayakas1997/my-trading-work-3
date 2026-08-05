import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.exponential_smoothing.compute import compute


def _make_bars(n: int = 100, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    open_p = close + np.random.randn(n) * 0.2
    high = np.maximum(close, open_p) + np.abs(np.random.randn(n) * 0.3)
    low = np.minimum(close, open_p) - np.abs(np.random.randn(n) * 0.3)
    return pd.DataFrame({"open": open_p, "high": high, "low": low, "close": close}, index=dates)


def test_no_data_returns_status_no_data():
    df = compute("AAPL", bars=None)
    row = df.iloc[0]
    assert row["status"] == "no_data"
    assert row["symbol"] == "AAPL"
    assert row["angle"] == "exponential_smoothing"


def test_empty_bars_returns_status_no_data():
    df = compute("AAPL", bars=pd.DataFrame())
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=3))
    row = df.iloc[0]
    assert row["status"] == "insufficient_data"
    assert row["n_observations"] == 3


def test_fits_and_forecasts():
    bars = _make_bars(n=120)
    df = compute("AAPL", bars=bars)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["angle"] == "exponential_smoothing"
    assert row["n_observations"] == 120

    # Point forecast is a finite float.
    assert np.isfinite(row["forecast"])

    # Smoothing parameters (alpha for level, beta for trend) are within
    # the valid [0, 1] range Holt's method optimizes over.
    assert 0.0 <= row["alpha"] <= 1.0
    assert 0.0 <= row["beta"] <= 1.0

    # Level/trend decomposition present and finite.
    assert np.isfinite(row["level"])
    assert row["trend"] is not None
    assert np.isfinite(row["trend"])

    assert np.isfinite(row["sse"])
    assert row["sse"] >= 0


def test_forecast_close_to_recent_level_on_flat_series():
    # A near-constant series: the one-step forecast should land close to
    # the constant level, not diverge wildly.
    np.random.seed(1)
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 200 + np.random.randn(n) * 0.05
    bars = pd.DataFrame({
        "open": close, "high": close + 0.1, "low": close - 0.1, "close": close,
    }, index=dates)

    df = compute("GOOG", bars=bars)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert abs(row["forecast"] - 200) < 2.0
