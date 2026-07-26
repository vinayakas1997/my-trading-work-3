import pandas as pd
import numpy as np
from datetime import datetime, timezone

from vinu_initial_analysis.angles.shock_clustering.compute import (
    _detect_shock_dates,
    _compute_shock_clusters,
    compute,
)


def _make_bars(n: int = 100, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    open_p = close + np.random.randn(n) * 0.2
    high = np.maximum(close, open_p) + np.abs(np.random.randn(n) * 0.3)
    low = np.minimum(close, open_p) - np.abs(np.random.randn(n) * 0.3)
    return pd.DataFrame({
        "open": open_p, "high": high, "low": low, "close": close,
    }, index=dates)


def test_detect_shock_dates():
    bars = _make_bars(100)
    dates = _detect_shock_dates(bars, gap_std_threshold=1.5)
    assert isinstance(dates, list)


def test_detect_shock_dates_high_threshold():
    bars = _make_bars(100)
    dates = _detect_shock_dates(bars, gap_std_threshold=10.0, vol_z_threshold=10.0)
    assert len(dates) == 0


def test_compute_shock_clusters_single_symbol():
    np.random.seed(42)
    prices = {"TEST": np.cumprod(1 + np.random.randn(100) * 0.01)}
    result = _compute_shock_clusters("TEST", prices, [], pd.date_range("2024-01-01", periods=100))
    assert result["status"] == "single_symbol"


def test_compute_shock_clusters_two_symbols():
    np.random.seed(42)
    common = np.random.randn(100) * 0.01
    prices = {
        "AAPL": np.cumprod(1 + common + np.random.randn(100) * 0.005),
        "GOOGL": np.cumprod(1 + common + np.random.randn(100) * 0.005),
    }
    result = _compute_shock_clusters("AAPL", prices, [], pd.date_range("2024-01-01", periods=100))
    assert result["status"] == "ok"
    assert len(result["cluster_members"]) > 0


def test_compute_empty_bars():
    result = compute("TEST", bars=None)
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_empty_dataframe():
    result = compute("TEST", bars=pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_full():
    bars = _make_bars(100)
    result = compute("TEST", bars=bars)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["angle"] == "shock_clustering"
