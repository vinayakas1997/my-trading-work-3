import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.arima.compute import compute


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
    assert row["angle"] == "arima"


def test_empty_bars_returns_status_no_data():
    df = compute("AAPL", bars=pd.DataFrame())
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=10))
    row = df.iloc[0]
    assert row["status"] == "insufficient_data"
    assert row["n_observations"] == 10


def test_fits_and_forecasts_with_confidence_interval():
    df = compute("AAPL", bars=_make_bars(n=150))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["angle"] == "arima"
    assert row["n_observations"] == 150

    # Point forecast must be a finite float.
    forecast = row["forecast"]
    assert np.isfinite(forecast)

    # Confidence interval must be a 2-element [lower, upper] bracket that
    # actually contains the point forecast, and be finite.
    ci = row["confidence_interval"]
    assert len(ci) == 2
    lower, upper = ci
    assert np.isfinite(lower) and np.isfinite(upper)
    assert lower <= forecast <= upper
    assert lower < upper

    # Order dict has the expected (p, d, q) keys.
    order = row["order"]
    assert set(order.keys()) == {"p", "d", "q"}
    assert all(isinstance(v, int) for v in order.values())

    assert np.isfinite(row["aic"])
    assert row["confidence_level"] == 0.95


def test_different_seeds_give_different_forecasts():
    df1 = compute("AAPL", bars=_make_bars(n=120, seed=1))
    df2 = compute("AAPL", bars=_make_bars(n=120, seed=2))
    assert df1.iloc[0]["forecast"] != df2.iloc[0]["forecast"]
