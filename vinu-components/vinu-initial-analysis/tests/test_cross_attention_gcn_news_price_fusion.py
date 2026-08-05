import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.cross_attention_gcn_news_price_fusion.compute import compute


def _make_bars(n: int = 60, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({"close": close}, index=dates)


def _make_news(n: int = 5) -> list[dict]:
    headlines = [
        "Company beats earnings expectations amid strong demand",
        "Regulators launch investigation into pricing practices",
        "New product launch drives investor optimism",
        "Analyst downgrades stock citing margin pressure",
        "Merger talks reported by sources close to the deal",
    ]
    return [{"title": h} for h in headlines[:n]]


def test_no_data_returns_status_no_data():
    df = compute("AAPL", bars=None, news=_make_news())
    assert df.iloc[0]["status"] == "no_data"


def test_insufficient_data_status():
    df = compute("AAPL", bars=_make_bars(n=5), news=_make_news())
    assert df.iloc[0]["status"] == "insufficient_data"


def test_runs_without_news():
    """news=[] must still produce a valid ok row — the bag-of-words vector
    degrades to all-zeros rather than erroring."""
    df = compute("AAPL", bars=_make_bars(), news=[])
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["n_news_articles_used"] == 0
    assert np.isfinite(row["predicted_next_return"])


def test_cross_attention_fusion_with_news():
    df = compute("AAPL", bars=_make_bars(), news=_make_news())
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["model_backend"] == "trained_in_process"
    assert row["n_news_articles_used"] == 5
    assert "1-node self-loop" in row["gcn_note"]
    assert np.isfinite(row["predicted_next_return"])
    assert np.isfinite(row["predicted_next_close"])
    assert row["predicted_next_close"] == row["last_close"] * (1 + row["predicted_next_return"])


def test_deterministic_across_calls_same_process():
    """Module weights are cached per-process (random init once) — same
    inputs should give the same output within one process/test run."""
    df1 = compute("AAPL", bars=_make_bars(), news=_make_news())
    df2 = compute("AAPL", bars=_make_bars(), news=_make_news())
    assert df1.iloc[0]["predicted_next_return"] == df2.iloc[0]["predicted_next_return"]
