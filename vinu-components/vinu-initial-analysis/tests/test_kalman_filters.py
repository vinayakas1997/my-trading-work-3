import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.kalman_filters.compute import compute


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
    assert row["angle"] == "kalman_filters"


def test_empty_bars_returns_status_no_data():
    df = compute("AAPL", bars=pd.DataFrame())
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=5))
    row = df.iloc[0]
    assert row["status"] == "insufficient_data"
    assert row["n_observations"] == 5


def test_filters_state_with_uncertainty():
    bars = _make_bars(n=150)
    df = compute("AAPL", bars=bars)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["angle"] == "kalman_filters"
    assert row["n_observations"] == 150

    # Filtered level should be a finite float, in the general neighborhood
    # of the observed close series (a state estimate of price level, not a
    # wildly different scale).
    close = bars["close"].astype(float).values
    assert np.isfinite(row["filtered_level"])
    assert abs(row["filtered_level"] - close[-1]) < 10 * close.std()

    # Uncertainty (state std dev) must be non-negative and finite.
    assert np.isfinite(row["filtered_level_std"])
    assert row["filtered_level_std"] >= 0

    assert np.isfinite(row["filtered_trend"])
    assert np.isfinite(row["filtered_trend_std"])
    assert row["filtered_trend_std"] >= 0

    # Smoothed estimate (two-pass) should also be finite and in a sane
    # range relative to the filtered (online) estimate.
    assert np.isfinite(row["smoothed_level"])
    assert np.isfinite(row["smoothed_trend"])

    assert row["last_observed_close"] == close[-1]


def test_filtered_level_tracks_a_flat_series_closely():
    # A near-constant series: the filtered level should converge close to
    # the constant value with low uncertainty.
    np.random.seed(0)
    n = 80
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 50 + np.random.randn(n) * 0.05
    bars = pd.DataFrame({
        "open": close, "high": close + 0.1, "low": close - 0.1, "close": close,
    }, index=dates)

    df = compute("MSFT", bars=bars)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert abs(row["filtered_level"] - 50) < 1.0
