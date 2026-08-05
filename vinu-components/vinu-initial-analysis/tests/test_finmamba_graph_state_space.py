import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.finmamba_graph_state_space.compute import compute


def _make_bars(n: int = 60, seed: int = 42) -> pd.DataFrame:
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


def test_fallback_proxy_honest_about_unconfirmed_availability():
    df = compute("AAPL", bars=_make_bars(n=40))
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "fallback_proxy"
    assert "unconfirmed" in row["fallback_reason"]
    assert "single-node graph" in row["graph_note"]
    assert row["predicted_movement"] in ("up", "down", "flat")
    assert 0.0 <= row["movement_confidence"] <= 1.0
    assert np.isfinite(row["predicted_next_close"])
