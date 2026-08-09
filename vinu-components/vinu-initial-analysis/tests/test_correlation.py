import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.news_price_causality.correlation import (
    compute_correlation,
    compute_lag_analysis,
    resample_news_to_hourly,
    resample_returns_to_hourly,
)


def test_resample_news_to_hourly():
    articles = [
        {"sort_ts": 1000, "sentiment_score": 5, "impact_label": "high_bullish"},
        {"sort_ts": 1500, "sentiment_score": -3, "impact_label": "high_bearish"},
        {"sort_ts": 4500, "sentiment_score": 0, "impact_label": "low"},
    ]
    df = resample_news_to_hourly(articles)
    assert len(df) == 2
    assert "article_count" in df.columns
    assert "avg_sentiment" in df.columns


def test_resample_returns_to_hourly():
    candles = [
        {"bar_ts": 100, "open": 100, "close": 105},
        {"bar_ts": 2000, "open": 105, "close": 102},
        {"bar_ts": 4000, "open": 102, "close": 108},
    ]
    df = resample_returns_to_hourly(candles)
    assert len(df) >= 1
    assert "return" in df.columns


def test_compute_correlation():
    news = pd.DataFrame({
        "hour_ts": [3600 * i for i in range(24)],
        "article_count": np.random.poisson(2, 24),
        "avg_sentiment": np.random.uniform(-5, 5, 24),
        "avg_impact": np.random.uniform(0, 2, 24),
    })
    returns = pd.DataFrame({
        "hour_ts": [3600 * i for i in range(24)],
        "return": np.random.normal(0, 1, 24),
    })
    result = compute_correlation(news, returns)
    assert "news_return_corr" in result
    assert "corr_ci_lower" in result
    assert "corr_ci_upper" in result
    assert "sample_size" in result


def test_compute_correlation_ci_is_not_degenerate_full_range():
    # Regression test for a fixed bug: compute_correlation's bootstrap CI
    # was always the degenerate [-1, 1] regardless of real correlation
    # strength, due to an un-paired resample (scipy.stats.bootstrap
    # decorrelated x from y per resample). Same root cause and fix as
    # _helpers.pearson_with_ci (known-issues.md Resolved #1/#5).
    rng = np.random.default_rng(3)
    n = 120
    article_count = rng.integers(0, 5, n)
    returns = 0.6 * article_count + rng.normal(0, 1, n)  # real, strong correlation
    news = pd.DataFrame({
        "hour_ts": [3600 * i for i in range(n)],
        "article_count": article_count,
        "avg_sentiment": rng.uniform(-5, 5, n),
        "avg_impact": rng.uniform(0, 2, n),
    })
    returns_df = pd.DataFrame({"hour_ts": [3600 * i for i in range(n)], "return": returns})

    result = compute_correlation(news, returns_df)
    assert result["news_return_corr"] > 0.3
    # a real, informative band -- not the old degenerate full-range bug
    assert result["corr_ci_lower"] > -1.0
    assert result["corr_ci_upper"] < 1.0
    assert result["corr_ci_upper"] - result["corr_ci_lower"] < 1.5


def test_compute_correlation_insufficient_data():
    news = pd.DataFrame({"hour_ts": [3600], "article_count": [1],
                          "avg_sentiment": [0], "avg_impact": [0]})
    returns = pd.DataFrame({"hour_ts": [3600], "return": [0.1]})
    result = compute_correlation(news, returns)
    assert result["sample_size"] < 5


def test_lag_analysis():
    news = pd.DataFrame({
        "hour_ts": [3600 * i for i in range(48)],
        "article_count": [1 if i % 5 == 0 else 0 for i in range(48)],
    })
    returns = pd.DataFrame({
        "hour_ts": [3600 * i for i in range(48)],
        "return": [0.5 if i % 5 == 1 else 0 for i in range(48)],
    })
    result = compute_lag_analysis(news, returns)
    assert "best_lag_minutes" in result
    assert "lag_results" in result
