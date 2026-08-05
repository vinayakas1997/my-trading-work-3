import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.garch.compute import compute


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
    assert row["angle"] == "garch"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=5))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fits_and_forecasts_positive_volatility():
    df = compute("AAPL", bars=_make_bars(n=200))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["next_period_volatility_forecast"] > 0
    assert 0.0 <= row["alpha"] <= 1.0
    assert 0.0 <= row["beta"] <= 1.0
    assert row["persistence"] == row["alpha"] + row["beta"]
    assert row["n_observations"] == 199  # pct_change drops the first row


def test_matches_shock_personality_vol_persistence_fit():
    """Same underlying garch_volatility() call as shock_personality — same
    input should produce the same alpha/beta/omega fit (not coincidentally
    similar; this is the whole point of extracting rather than
    reimplementing)."""
    from vinu_initial_analysis.angles.shock_personality.compute import _compute_vol_persistence

    bars = _make_bars(n=150)
    garch_row = compute("AAPL", bars=bars).iloc[0]
    shock_personality_result = _compute_vol_persistence("AAPL", bars)

    assert garch_row["alpha"] == shock_personality_result["alpha"]
    assert garch_row["beta"] == shock_personality_result["beta"]
    assert garch_row["omega"] == shock_personality_result["omega"]
