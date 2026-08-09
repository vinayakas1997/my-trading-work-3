import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.chronos.compute import compute


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
    assert row["symbol"] == "AAPL"
    assert row["angle"] == "chronos"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=10))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_real_pretrained_pipeline_forecasts_expected_length():
    """Genuine integration test: loads amazon/chronos-t5-large via the real
    chronos-forecasting package and checks the forecast shape/finiteness.
    Network access + first-run HF Hub download required; the pipeline is
    cached module-wide by compute()'s _PIPELINE_CACHE so a second test in
    this file/process reuses the already-loaded model. n=512 matches the
    decided MIN_OBSERVATIONS (a fixed context requirement, not a floor —
    see 04-enhancement-of-each-angle/03-chronos.md SS3)."""
    df = compute("AAPL", bars=_make_bars(n=512))
    row = df.iloc[0]
    assert row["status"] == "ok"
    # Honest either/or: if the real package/network isn't available in some
    # other environment this runs in, the angle still degrades cleanly.
    assert row["model_backend"] in ("pretrained", "fallback_proxy")
    assert len(row["median_forecast"]) == row["forecast_horizon"] == 5
    assert all(np.isfinite(row["median_forecast"]))
    assert all(np.isfinite(row["p10_forecast"]))
    assert all(np.isfinite(row["p90_forecast"]))
    assert np.all(np.array(row["p10_forecast"]) <= np.array(row["p90_forecast"]) + 1e-6)


def test_pretrained_backend_actually_loads_in_this_environment():
    """This environment does have chronos-forecasting installed with network
    access verified during implementation — assert the real path is taken,
    not silently degrading to the proxy, and that the decided checkpoint
    (chronos-t5-large, upgraded from tiny) is what actually loads."""
    df = compute("MSFT", bars=_make_bars(n=512, seed=7))
    row = df.iloc[0]
    assert row["model_backend"] == "pretrained"
    assert row["checkpoint"] == "amazon/chronos-t5-large"
    assert row["fallback_reason"] is None
