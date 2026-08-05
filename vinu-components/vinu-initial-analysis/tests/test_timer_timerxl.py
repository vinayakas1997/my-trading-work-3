import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.timer_timerxl.compute import compute


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


def test_fallback_proxy_for_sub_patch_context():
    """Fewer than one 96-point patch cannot feed the model, so it must
    degrade to the statistical proxy rather than crash."""
    df = compute("AAPL", bars=_make_bars(n=64))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert row["n_patches"] < 1
    assert len(row["point_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["point_forecast"]))


def test_real_pretrained_model_forecasts_expected_length():
    """Genuine integration test: loads thuml/timer-base-84m via the shared
    models dir and checks the forecast shape/finiteness. Network access +
    first-run HF Hub download required; the model is cached module-wide by
    compute()'s _MODEL_CACHE."""
    df = compute("AAPL", bars=_make_bars(n=500))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] in ("pretrained", "fallback_proxy")
    assert len(row["point_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["point_forecast"]))
    assert all(np.isfinite(row["p10_forecast"]))
    assert all(np.isfinite(row["p90_forecast"]))
    assert np.all(np.array(row["p10_forecast"]) <= np.array(row["p90_forecast"]) + 1e-6)


def test_pretrained_backend_actually_loads_in_this_environment():
    """This environment has the weights downloaded and transformers installed
    with network access verified during implementation — assert the real path
    is taken, not silently degrading to the proxy."""
    df = compute("MSFT", bars=_make_bars(n=500, seed=7))
    row = df.iloc[0]
    assert row["model_backend"] == "pretrained"
    assert row["checkpoint"] == "thuml/timer-base-84m"
    assert row["fallback_reason"] is None
