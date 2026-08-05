import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.moirai.compute import compute


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


def test_fallback_proxy_and_any_variate_note():
    df = compute("AAPL", bars=_make_bars(n=60))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert "uni2ts" in row["fallback_reason"]
    assert "single-ticker" in row["any_variate_note"] or "single-variate" in row["any_variate_note"]
    assert len(row["point_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["point_forecast"]))
    assert np.all(np.array(row["p10_forecast"]) <= np.array(row["p90_forecast"]) + 1e-6)
