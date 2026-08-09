from __future__ import annotations

import numpy as np

from vinu_initial_analysis.angles.news_price_causality.backtest import (
    _quarter_key,
    run_aggregate_tests_backtest,
    run_impact_backtest,
)

# ~2 real calendar quarters of hourly bars -- hourly (not 1-minute) cadence
# keeps synthetic fixture generation/test runtime small; the resampling
# logic under test (Granger/correlation/lag all operate on hourly buckets
# regardless of the source cadence) doesn't need finer bars to exercise
# correctly. Real-data validation (02-real-scenario.md) uses the project's
# real 1-minute cache instead.
_START_TS = 1_700_000_000  # 2023-11-14T22:13:20Z


def _make_candles(n_hours: int, seed: int = 1) -> list[dict]:
    rng = np.random.default_rng(seed)
    price = 100.0
    candles = []
    for i in range(n_hours):
        ts = _START_TS + i * 3600
        open_p = price
        price = max(price + rng.normal(0, 0.5), 1.0)
        candles.append({
            "bar_ts": ts, "open": open_p, "close": price,
            "high": max(open_p, price), "low": min(open_p, price), "volume": 1000,
        })
    return candles


def _make_articles(candles: list[dict], every_n_hours: int = 3, seed: int = 2) -> list[dict]:
    # Poisson-ish variable article count per hour (not a fixed 0-or-1
    # cadence) -- a constant article_count-per-bucket makes
    # news_intensity a zero-variance series, and pearsonr correctly
    # returns NaN for a constant input (confirmed real scipy behavior,
    # not a code bug) -- caught by this test's own first draft.
    rng = np.random.default_rng(seed)
    articles = []
    counter = 0
    for i, c in enumerate(candles):
        if i % every_n_hours != 0:
            continue
        n_articles = int(rng.poisson(1.5))
        for _ in range(n_articles):
            counter += 1
            articles.append({
                "id": f"a{counter}",
                "headline": f"Real-shaped headline text number {counter} about the company outlook",
                "sort_ts": c["bar_ts"] + int(rng.integers(0, 3000)),
                "tickers": ["AAPL"],
                "sentiment": "NEUTRAL",
                "sentiment_score": int(rng.integers(-5, 6)),
                "category": "earnings",
                "priority": "normal",
                "finbert_score": float(rng.uniform(-1, 1)),
                "thread_id": "",
            })
    return articles


def test_quarter_key_format():
    assert _quarter_key(_START_TS) == "2023-Q4"


def test_impact_backtest_produces_tagged_rows():
    candles = _make_candles(n_hours=24 * 30)  # one month, hourly
    articles = _make_articles(candles)
    df = run_impact_backtest("AAPL", candles, articles)
    impact_rows = df[df["type"] == "impact"]
    assert len(impact_rows) == len(articles)
    for _, row in impact_rows.iterrows():
        assert row["session"] is not None or row["session"] == "closed"
        assert "day_of_week" in row
        assert "quarter" in row
        assert row["symbol"] == "AAPL"


def test_impact_backtest_empty_inputs_produce_no_rows():
    df = run_impact_backtest("AAPL", [], [])
    assert df.empty


def test_aggregate_tests_backtest_produces_quarter_tagged_rows():
    # ~2 quarters of hourly bars, articles every 3 hours -- enough hourly
    # buckets per quarter to clear Granger's real >= 17-bucket floor.
    candles = _make_candles(n_hours=24 * 200)
    articles = _make_articles(candles, every_n_hours=3)
    df = run_aggregate_tests_backtest("AAPL", candles, articles)
    assert not df.empty
    assert set(df["type"].unique()) <= {"granger", "correlation", "lag", "significance_model_eval"}
    for _, row in df.iterrows():
        assert row["quarter_key"]  # e.g. "2023-Q4"

    correlation_rows = df[df["type"] == "correlation"]
    assert len(correlation_rows) >= 1
    for _, row in correlation_rows.iterrows():
        assert -1.0 <= row["news_return_corr"] <= 1.0


def test_aggregate_tests_backtest_empty_inputs_produce_no_rows():
    df = run_aggregate_tests_backtest("AAPL", [], [])
    assert df.empty
