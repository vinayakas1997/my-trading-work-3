import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.timesfm.compute import compute


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
    assert row["angle"] == "timesfm"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=10))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_real_pretrained_checkpoint_forecasts_expected_length():
    """Genuine integration test: loads google/timesfm-2.5-200m-pytorch via
    the real timesfm[torch] package. First run downloads ~800MB from the
    HF Hub (cached under ~/.cache/huggingface); the model is cached
    module-wide by compute()'s _MODEL_CACHE so later tests in this process
    reuse it instead of reloading."""
    df = compute("AAPL", bars=_make_bars(n=200))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] in ("pretrained", "fallback_proxy")
    assert len(row["point_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["point_forecast"]))
    assert all(np.isfinite(row["p10_forecast"]))
    assert all(np.isfinite(row["p90_forecast"]))


def test_pretrained_backend_actually_loads_in_this_environment():
    df = compute("MSFT", bars=_make_bars(n=200, seed=7))
    row = df.iloc[0]
    assert row["model_backend"] == "pretrained"
    assert row["checkpoint"] == "google/timesfm-2.5-200m-pytorch"
    assert row["fallback_reason"] is None
