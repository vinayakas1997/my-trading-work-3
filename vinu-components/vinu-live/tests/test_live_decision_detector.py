import numpy as np
import pandas as pd
import pytest

from vinu_live.live_decision.detector import compute_live_snapshot, min_warmup_bars


@pytest.fixture
def bars() -> pd.DataFrame:
    n = 260  # comfortably above sma_200's warmup
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    open_ = close + rng.normal(0, 0.3, n)
    volume = rng.uniform(1000, 5000, n)
    bar_ts = 1_700_000_000 + np.arange(n) * 900  # 15m bars
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": volume, "bar_ts": bar_ts,
    })


def test_min_warmup_bars_is_positive_and_reasonable():
    n = min_warmup_bars()
    assert n > 0
    # sma_200 alone needs on the order of 200+ bars of warmup.
    assert n >= 200


def test_snapshot_has_no_new_indicator_math_missing_expected_keys(bars):
    snapshot = compute_live_snapshot(bars)
    for key in (
        "adx_14", "rsi_14", "sma_200", "ema_200", "atr_14",
        "stoch_k_14", "stoch_d_14", "macd_line", "macd_histogram",
        "bollinger_band_width", "bollinger_percent_b",
        "dist_from_sma_5", "dist_from_ema_5",
        "volume_vs_avg20", "vwap_dist",
        "accumulation_distribution_line", "obv",
    ):
        assert key in snapshot, f"missing {key}"


def test_snapshot_values_are_finite_once_warmed_up(bars):
    snapshot = compute_live_snapshot(bars)
    # With 260 bars, every indicator (even sma_200) should have a real value.
    for key, value in snapshot.items():
        if value is not None:
            assert np.isfinite(value), f"{key} is not finite: {value}"


def test_dist_from_sma_matches_manual_formula(bars):
    snapshot = compute_live_snapshot(bars)
    close_last = float(bars["close"].iloc[-1])
    sma_5 = snapshot["sma_5"]
    expected = (close_last - sma_5) / sma_5
    assert snapshot["dist_from_sma_5"] == pytest.approx(expected)


def test_macd_histogram_is_line_minus_signal(bars):
    snapshot = compute_live_snapshot(bars)
    if snapshot["macd_line"] is not None and snapshot["macd_signal"] is not None:
        assert snapshot["macd_histogram"] == pytest.approx(
            snapshot["macd_line"] - snapshot["macd_signal"]
        )


def test_too_few_bars_returns_none_for_long_lookback_indicators():
    n = 30  # well under sma_200's warmup, above sma_5's
    close = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, n)))
    bars = pd.DataFrame({
        "open": close, "high": close + 0.5, "low": close - 0.5,
        "close": close, "volume": np.full(n, 1000.0),
        "bar_ts": 1_700_000_000 + np.arange(n) * 900,
    })
    snapshot = compute_live_snapshot(bars)
    assert snapshot["sma_200"] is None
    assert snapshot["sma_5"] is not None


def test_empty_bars_returns_empty_snapshot():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "bar_ts"])
    assert compute_live_snapshot(empty) == {}


def test_missing_required_column_raises():
    bad = pd.DataFrame({"close": [1.0, 2.0]})
    with pytest.raises(ValueError):
        compute_live_snapshot(bad)
