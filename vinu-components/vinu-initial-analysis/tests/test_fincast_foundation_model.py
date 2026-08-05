import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.fincast_foundation_model.compute import compute


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
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=10))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fallback_proxy_honest_about_unconfirmed_availability():
    df = compute("AAPL", bars=_make_bars(n=80))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert "unconfirmed" in row["fallback_reason"]
    assert "FinCast" in row["fallback_reason"]
    for field in ("predicted_next_open", "predicted_next_high", "predicted_next_low", "predicted_next_close"):
        assert np.isfinite(row[field])
