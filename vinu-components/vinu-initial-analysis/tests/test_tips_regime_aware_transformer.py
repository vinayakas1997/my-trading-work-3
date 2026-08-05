import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.tips_regime_aware_transformer.compute import compute


def _make_bars(n: int = 220, seed: int = 42) -> pd.DataFrame:
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


def _make_trending_bars(n: int = 220, seed: int = 3, phi: float = 0.5) -> pd.DataFrame:
    """A momentum-regime series, built directly from an AR(1) return
    process with positive serial correlation (r_t = phi*r_{t-1} + eps_t,
    phi>0) — this is what actually gives positive lag-1 return
    autocorrelation (the regime detector's statistic), unlike a smooth
    price-level drift, whose local return autocorrelation over a rolling
    window is dominated by noise, not the drift itself. Used to
    sanity-check the regime detector leans momentum here rather than
    always returning the same label regardless of input."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    eps = rng.randn(n) * 0.01
    r = np.zeros(n)
    for t in range(1, n):
        r[t] = phi * r[t - 1] + eps[t]
    close = 100 * np.cumprod(1 + r)
    open_p = close * (1 + rng.randn(n) * 0.001)
    high = np.maximum(close, open_p) * (1 + np.abs(rng.randn(n) * 0.0015))
    low = np.minimum(close, open_p) * (1 - np.abs(rng.randn(n) * 0.0015))
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
    assert row["angle"] == "tips_regime_aware_transformer"


def test_insufficient_data_status():
    # Below MIN_BARS=120 — not enough history for both the trailing
    # regime-autocorrelation window and the transformer's training windows.
    df = compute("AAPL", bars=_make_bars(n=60))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fits_forecasts_and_exposes_regime_label():
    df = compute("AAPL", bars=_make_bars(n=220))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert np.isfinite(row["forecast_price"])
    assert np.isfinite(row["forecast_return"])
    assert row["direction"] in ("up", "down", "flat")
    # Regime-detection auxiliary output, per 24-tips-...md's spec.
    assert row["regime"] in ("momentum", "mean_reversion")
    assert np.isfinite(row["regime_autocorr"])
    assert -1.0 <= row["regime_autocorr"] <= 1.0
    assert row["n_momentum_windows"] + row["n_mean_reversion_windows"] == row["n_train_windows"]
    assert np.isfinite(row["train_loss"])


def test_regime_detector_responds_to_strongly_trending_input():
    df = compute("TREND", bars=_make_trending_bars(n=220))
    row = df.iloc[0]
    assert row["status"] == "ok"
    # A near-monotonic trend has strong positive lag-1 return autocorrelation
    # -> should be classified momentum, not mean_reversion.
    assert row["regime"] == "momentum"
    assert row["regime_autocorr"] > 0


def test_deterministic_with_fixed_seed():
    bars = _make_bars(n=220)
    df1 = compute("AAPL", bars=bars, seed=7)
    df2 = compute("AAPL", bars=bars, seed=7)
    assert df1.iloc[0]["forecast_price"] == df2.iloc[0]["forecast_price"]
    assert df1.iloc[0]["forecast_return"] == df2.iloc[0]["forecast_return"]
    assert df1.iloc[0]["regime"] == df2.iloc[0]["regime"]
