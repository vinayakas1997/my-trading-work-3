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
