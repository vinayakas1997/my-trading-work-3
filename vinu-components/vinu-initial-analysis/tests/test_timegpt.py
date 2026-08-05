import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.timegpt.compute import compute


def _make_bars(n: int = 100, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({"close": close}, index=dates)


def test_no_data_returns_status_no_data():
    df = compute("AAPL", bars=None)
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=5))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_always_fallback_proxy_since_no_api_key():
    df = compute("AAPL", bars=_make_bars(n=50))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert "paid hosted API" in row["fallback_reason"]
    assert not row["api_key_configured"]
    assert len(row["point_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["point_forecast"]))
    assert all(np.isfinite(row["lo_80_forecast"]))
    assert all(np.isfinite(row["hi_80_forecast"]))
