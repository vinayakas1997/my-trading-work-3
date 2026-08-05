import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.lag_llama.compute import compute


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


def test_fallback_proxy_emits_full_quantile_distribution():
    df = compute("AAPL", bars=_make_bars(n=80))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert "lag-llama has no PyPI package" in row["fallback_reason"]
    assert row["quantile_levels"] == [0.05, 0.25, 0.5, 0.75, 0.95]
    quantiles = row["quantile_forecasts"]
    assert set(quantiles.keys()) == {"0.05", "0.25", "0.5", "0.75", "0.95"}
    for q in quantiles.values():
        assert len(q) == row["forecast_horizon"] == 5
        assert all(np.isfinite(q))
    # monotonic across quantile levels at each forecast step
    p05 = np.array(quantiles["0.05"])
    p50 = np.array(quantiles["0.5"])
    p95 = np.array(quantiles["0.95"])
    assert np.all(p05 <= p50 + 1e-9)
    assert np.all(p50 <= p95 + 1e-9)
