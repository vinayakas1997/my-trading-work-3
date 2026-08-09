from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.shock_personality.backtest import run_shock_backtest
from vinu_initial_analysis.angles.shock_personality.compute import (
    MIN_OBSERVATIONS,
    _compute_drift_metrics,
    _compute_gap_fill_rate,
    _compute_vol_persistence,
    _cross_reference_news,
    _detect_gap_shocks,
    _detect_vol_shocks,
    _tag_shocks,
    compute,
)

_START_TS = 1_672_531_200  # 2023-01-01T00:00:00Z


def _make_bars(n: int = 100, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_p = close + rng.normal(0, 0.2, size=n)
    high = np.maximum(close, open_p) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(close, open_p) - np.abs(rng.normal(0, 0.3, size=n))
    bar_ts = [_START_TS + i * 86400 for i in range(n)]
    return pd.DataFrame({"bar_ts": bar_ts, "open": open_p, "high": high, "low": low, "close": close})


def _make_bars_with_gap_shock(n: int = 60, shock_idx: int = 30) -> pd.DataFrame:
    bars = _make_bars(n)
    bars.loc[shock_idx, "open"] = bars.loc[shock_idx - 1, "close"] * 1.15
    bars.loc[shock_idx, "high"] = max(bars.loc[shock_idx, "high"], bars.loc[shock_idx, "open"] * 1.01)
    return bars


def test_detect_gap_shocks():
    bars = _make_bars_with_gap_shock()
    shocks = _detect_gap_shocks(bars, gap_std_threshold=1.5)
    assert len(shocks) > 0
    assert all(s["type"] == "gap" for s in shocks)


def test_detect_gap_shocks_no_shocks():
    bars = _make_bars(60)
    shocks = _detect_gap_shocks(bars, gap_std_threshold=10.0)
    assert len(shocks) == 0


def test_detect_vol_shocks():
    bars = _make_bars(100)
    shocks = _detect_vol_shocks(bars, vol_z_threshold=1.5)
    assert isinstance(shocks, list)


def test_cross_reference_news():
    shocks = [{"date": _START_TS + 10 * 86400, "type": "gap", "magnitude": 0.02}]
    news = [{"published_at": "2023-01-09T12:00:00"}]
    result = _cross_reference_news(shocks, news, news_window_days=2)
    assert result[0]["has_news"] is True


def test_cross_reference_news_no_match():
    shocks = [{"date": _START_TS + 10 * 86400, "type": "gap", "magnitude": 0.02}]
    news = [{"published_at": "2023-02-01T12:00:00"}]
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


def test_compute_drift_metrics_reports_both_views():
    bars = _make_bars(150)
    shocks = _tag_shocks(bars)
    result = _compute_drift_metrics(bars, shocks, max_lag=20)
    assert set(result.keys()) == {"drift_persistence_days", "drift_mean_autocorr"}
    assert "mean_days" in result["drift_persistence_days"]
    assert "mean" in result["drift_mean_autocorr"]


def test_compute_empty_bars():
    result = compute("TEST", bars=None)
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_empty_dataframe():
    result = compute("TEST", bars=pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "no_data"


def test_compute_insufficient_data_below_floor():
    bars = _make_bars(MIN_OBSERVATIONS - 1)
    result = compute("TEST", bars=bars)
    assert result.iloc[0]["status"] == "insufficient_data"


def test_compute_full_reports_news_split_and_drift_autocorr():
    bars = _make_bars(200)
    news = [{"published_at": "2023-06-15T12:00:00"}]
    result = compute("TEST", bars=bars, news=news)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["angle"] == "shock_personality"
    assert row["status"] == "ok"
    for field in (
        "gap_fill_rate", "gap_fill_rate_news", "gap_fill_rate_no_news",
        "drift_persistence_days", "drift_mean_autocorr",
        "drift_persistence_days_news", "drift_persistence_days_no_news",
        "n_shocks_with_news",
    ):
        assert field in row


def test_compute_without_news():
    bars = _make_bars(200)
    result = compute("TEST", bars=bars, news=None)
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["status"] == "ok"
    assert result.iloc[0]["n_shocks_with_news"] == 0


def test_shock_backtest_produces_date_only_tagged_gap_rows():
    bars = _make_bars_with_gap_shock()
    df = run_shock_backtest("TEST", bars, time_format="1D")
    assert not df.empty
    gap_rows = df[df["type"] == "gap"]
    assert not gap_rows.empty
    assert "session" not in gap_rows.columns
    for col in ("day_of_week", "week_of_month", "month", "quarter", "has_news", "nearest_news_days"):
        assert col in df.columns


def test_shock_backtest_empty_below_floor():
    bars = _make_bars(MIN_OBSERVATIONS - 1)
    df = run_shock_backtest("TEST", bars)
    assert df.empty
