import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.tft.compute import compute


def _make_bars(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(rng.randn(n) * 0.5)
    open_p = close + rng.randn(n) * 0.2
    high = np.maximum(close, open_p) + np.abs(rng.randn(n) * 0.3)
    low = np.minimum(close, open_p) - np.abs(rng.randn(n) * 0.3)
    volume = np.abs(rng.randn(n) * 1000 + 5000)
    return pd.DataFrame(
        {"open": open_p, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def test_no_data_returns_status_no_data():
    df = compute("AAPL", bars=None)
    row = df.iloc[0]
    assert row["status"] == "no_data"
    assert row["symbol"] == "AAPL"
    assert row["angle"] == "tft"


def test_insufficient_data_status():
    # Below MIN_BARS=90 — not enough post-feature-warmup sliding windows.
    df = compute("AAPL", bars=_make_bars(n=40))
    assert df.iloc[0]["status"] == "insufficient_data"


def test_fits_and_forecasts_quantiles_are_ordered_and_finite():
    df = compute("AAPL", bars=_make_bars(n=200))
    row = df.iloc[0]
    assert row["status"] == "ok"
    for col in ("forecast_return_p10", "forecast_return_p50", "forecast_return_p90",
                "forecast_price_p10", "forecast_price_p50", "forecast_price_p90"):
        assert np.isfinite(row[col])
    # Natively quantile output per 22-tft.md's spec — P10 <= P50 <= P90.
    assert row["forecast_return_p10"] <= row["forecast_return_p50"] <= row["forecast_return_p90"]
    assert row["forecast_price_p10"] <= row["forecast_price_p50"] <= row["forecast_price_p90"]
    assert row["direction"] in ("up", "down", "flat")
    # Variable-selection network output — one weight per engineered feature.
    weights = row["variable_selection_weights"]
    assert isinstance(weights, dict)
    assert len(weights) == 6
    assert all(np.isfinite(v) for v in weights.values())


def test_deterministic_with_fixed_seed():
    bars = _make_bars(n=200)
    df1 = compute("AAPL", bars=bars, seed=7)
    df2 = compute("AAPL", bars=bars, seed=7)
    assert df1.iloc[0]["forecast_return_p50"] == df2.iloc[0]["forecast_return_p50"]
    assert df1.iloc[0]["forecast_return_p10"] == df2.iloc[0]["forecast_return_p10"]
    assert df1.iloc[0]["forecast_return_p90"] == df2.iloc[0]["forecast_return_p90"]
