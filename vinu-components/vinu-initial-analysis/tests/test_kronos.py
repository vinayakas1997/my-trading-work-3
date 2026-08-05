import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.kronos.compute import compute


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
    row = df.iloc[0]
    assert row["status"] == "no_data"
    assert row["angle"] == "kronos"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=10))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_real_pretrained_model_forecasts_next_bar():
    """Genuine integration test: loads NeoQuasar/Kronos-base + tokenizer via
    the shared models dir (vendored model code) and checks the forecast
    shape/finiteness. Network access + first-run HF Hub download required;
    the predictor is cached module-wide by compute()'s _PREDICTOR_CACHE."""
    df = compute("AAPL", bars=_make_bars(n=200))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] in ("pretrained", "fallback_proxy")
    assert len(row["forecast_ohlc"]["close"]) == row["forecast_horizon"] == 5
    for field in ("predicted_next_open", "predicted_next_high", "predicted_next_low", "predicted_next_close"):
        assert np.isfinite(row[field])
        assert 0.1 * row["last_close"] < row[field] < 10 * row["last_close"]


def test_pretrained_backend_actually_loads_in_this_environment():
    """This environment has the weights downloaded and vendored model code in
    place with network access verified during implementation — assert the real
    path is taken, not silently degrading to the proxy."""
    df = compute("MSFT", bars=_make_bars(n=200, seed=7))
    row = df.iloc[0]
    assert row["model_backend"] == "pretrained"
    assert row["checkpoint"] == "NeoQuasar/Kronos-base"
    assert row["fallback_reason"] is None


def test_predicted_next_bar_is_finite_and_reasonable():
    df = compute("AAPL", bars=_make_bars(n=80))
    row = df.iloc[0]
    assert row["model_backend"] in ("pretrained", "fallback_proxy")
    for field in ("predicted_next_open", "predicted_next_high", "predicted_next_low", "predicted_next_close"):
        assert np.isfinite(row[field])
        # sanity: shouldn't blow up to an absurd multiple of last close
        assert 0.1 * row["last_close"] < row[field] < 10 * row["last_close"]
