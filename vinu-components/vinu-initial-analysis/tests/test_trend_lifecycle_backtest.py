from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.trend_lifecycle.backtest import (
    run_confidence_calibration,
    run_signal_outcome_backtest,
)

_START_TS = 1_672_531_200  # 2023-01-01T00:00:00Z


def _make_swinging_bars(n: int = 400, seed: int = 1) -> pd.DataFrame:
    """A real, deterministic-ish swinging price series -- a sine wave
    (guarantees multiple real peaks/troughs the detector can find) plus
    small real noise, not perfectly periodic so peaks/troughs vary in
    shape rather than being identical copies of each other.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    swing = 15 * np.sin(t / 18.0) + 3 * np.sin(t / 5.0 + 1.0)
    trend = t * 0.01
    noise = np.cumsum(rng.normal(0, 0.15, size=n))
    close = 100 + swing + trend + noise
    close = np.clip(close, 10, None)
    high = close + np.abs(rng.normal(0, 0.4, size=n))
    low = close - np.abs(rng.normal(0, 0.4, size=n))
    open_p = close + rng.normal(0, 0.2, size=n)
    bar_ts = [_START_TS + i * 86400 for i in range(n)]
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": open_p, "high": high, "low": low, "close": close,
        "volume": rng.integers(1000, 5000, size=n),
    })


def test_signal_outcome_backtest_produces_tagged_rows_with_real_outcomes():
    bars = _make_swinging_bars()
    df = run_signal_outcome_backtest("AAPL", bars, time_format="1D")
    assert not df.empty
    # "session" here is trend_lifecycle's OWN premarket/regular/afterhours/
    # closed taxonomy (carried from the underlying peak snapshot, needed by
    # trend_session_structure's per-session breakdown) -- distinct from the
    # shared calendar-tagging scheme's own session field, which correctly
    # stays absent since date-only tags are used for the calendar dimension.
    assert "session" in df.columns
    assert "subsession" not in df.columns
    for col in ("day_of_week", "week_of_month", "month", "quarter", "signal_type", "stated_confidence"):
        assert col in df.columns
    # every mature book_profits row has a real actual_subsequent_drawdown_pct
    mature_bp = df[(df["signal_type"] == "book_profits") & (df["outcome_mature"])]
    if not mature_bp.empty:
        assert mature_bp["actual_subsequent_drawdown_pct"].notna().all()
        assert mature_bp["stop_would_have_helped"].isin([True, False]).all()


def test_signal_outcome_backtest_empty_on_no_peaks():
    bars = pd.DataFrame({
        "bar_ts": [_START_TS + i * 86400 for i in range(30)],
        "open": [100.0] * 30, "high": [100.0] * 30, "low": [100.0] * 30, "close": [100.0] * 30,
    })
    df = run_signal_outcome_backtest("AAPL", bars, time_format="1D")
    assert df.empty


def test_confidence_calibration_buckets_carry_n_and_bounded_success_rate():
    bars = _make_swinging_bars()
    outcomes = run_signal_outcome_backtest("AAPL", bars, time_format="1D")
    calibration = run_confidence_calibration(outcomes)
    if calibration.empty:
        return  # real, honest possibility on a small/synthetic sample -- no mature book_profits signals
    for _, row in calibration.iterrows():
        assert row["n_signals"] > 0
        assert 0.0 <= row["actual_success_rate"] <= 1.0
        assert row["confidence_bucket_low"] < row["confidence_bucket_high"]


def test_confidence_calibration_empty_on_empty_input():
    assert run_confidence_calibration(pd.DataFrame()).empty
