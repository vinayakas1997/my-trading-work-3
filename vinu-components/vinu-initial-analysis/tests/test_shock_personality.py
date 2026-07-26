import pandas as pd
import numpy as np
from datetime import datetime, timezone

from vinu_initial_analysis.angles.shock_personality.compute import (
    _detect_gap_shocks,
    _detect_vol_shocks,
    _cross_reference_news,
    _compute_gap_fill_rate,
    _compute_vol_persistence,
    _compute_drift_persistence,
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


def _make_bars_with_gap_shock() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    close = np.ones(50) * 100.0
    open_p = np.ones(50) * 100.0
    open_p[25] = 105.0  # intentional gap
    close[25] = 100.0
    return pd.DataFrame({
        "open": open_p, "high": open_p + 1, "low": open_p - 1, "close": close,
    }, index=dates)


def test_detect_gap_shocks():
    bars = _make_bars_with_gap_shock()
    shocks = _detect_gap_shocks(bars, gap_std_threshold=1.5)
    assert len(shocks) > 0
    assert all(s["type"] == "gap" for s in shocks)


def test_detect_gap_shocks_no_shocks():
    bars = _make_bars(50)
    shocks = _detect_gap_shocks(bars, gap_std_threshold=10.0)
    assert len(shocks) == 0


def test_detect_vol_shocks():
    bars = _make_bars(100)
    shocks = _detect_vol_shocks(bars, vol_z_threshold=1.5)
    assert isinstance(shocks, list)


def test_cross_reference_news():
    shocks = [{"date": "2024-01-10", "type": "gap", "magnitude": 0.02}]
    news = [{"published_at": "2024-01-09T12:00:00"}]
    result = _cross_reference_news(shocks, news, news_window_days=2)
    assert result[0]["has_news"] is True


def test_cross_reference_news_no_match():
    shocks = [{"date": "2024-01-10", "type": "gap", "magnitude": 0.02}]
    news = [{"published_at": "2024-02-01T12:00:00"}]
    result = _cross_reference_news(shocks, news, news_window_days=2)
    assert result[0]["has_news"] is False


def test_compute_gap_fill_rate():
    bars = _make_bars_with_gap_shock()
    shocks = _detect_gap_shocks(bars, gap_std_threshold=1.5)
    result = _compute_gap_fill_rate(bars, shocks, fill_window=5)
    assert "mean" in result
    assert "n_observations" in result
    assert result["n_observations"] >= 0


def test_compute_vol_persistence():
    bars = _make_bars(200)
    result = _compute_vol_persistence("TEST", bars)
    assert result["status"] == "ok"
    assert result["alpha"] is not None
    assert result["beta"] is not None
    assert result["persistence"] is not None


def test_compute_drift_persistence():
    bars = _make_bars(100)
    from vinu_initial_analysis.angles.shock_personality.compute import _tag_shocks
    shocks = _tag_shocks(bars)
    result = _compute_drift_persistence(bars, shocks, max_lag=20)
    assert "mean_days" in result
    assert "n_observations" in result


def test_compute_empty_bars():
    result = compute("TEST", bars=None)
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_empty_dataframe():
    result = compute("TEST", bars=pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_full():
    bars = _make_bars(200)
    news = [{"published_at": "2024-06-15T12:00:00"}]
    result = compute("TEST", bars=bars, news=news)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["angle"] == "shock_personality"


def test_compute_without_news():
    bars = _make_bars(200)
    result = compute("TEST", bars=bars, news=None)
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "ok"
