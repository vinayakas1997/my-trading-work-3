import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.timer_timerxl.compute import (
    MIN_OBSERVATIONS,
    PATCH_SIZE,
    _fallback_forecast,
    compute,
)


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


def test_min_observations_clears_the_real_patch_requirement():
    # 04-enhancement-of-each-angle/27-timer_timerxl.md: MIN_OBSERVATIONS
    # was raised from 24 specifically because it sat below PATCH_SIZE=96 --
    # requests with 24-95 observations used to pass the insufficient_data
    # check, then hit the real model's n_patches<1 guard, and silently
    # fall through to the proxy. 100 > 96 makes that path unreachable via
    # compute()'s public API now.
    assert MIN_OBSERVATIONS > PATCH_SIZE


def test_below_floor_is_insufficient_data_not_a_silent_fallback():
    # A sub-patch-worthy 64 observations used to reach the model call and
    # silently degrade to fallback_proxy (the confusing path the design
    # doc flagged) -- now blocked at the floor before that ever happens.
    df = compute("AAPL", bars=_make_bars(n=64))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fallback_forecast_still_handles_sub_patch_data_directly():
    """The fallback proxy function itself (not compute()'s public API) must
    still degrade gracefully on fewer than one 96-point patch, since it's
    also reachable for real reasons unrelated to observation count (e.g. a
    package/network failure) with a short-history caller."""
    closes = _make_bars(n=64)["close"].values
    forecast = _fallback_forecast(closes)
    assert len(forecast["point_forecast"]) == 5
    assert all(np.isfinite(forecast["point_forecast"]))


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
