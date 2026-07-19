from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import pearsonr, bootstrap


def resample_news_to_hourly(articles: list[dict]) -> pd.DataFrame:
    import pandas as pd
    records = []
    for a in articles:
        ts = a.get("sort_ts", a.get("ts", 0))
        bucket = (ts // 3600) * 3600
        records.append({
            "hour_ts": bucket,
            "sentiment_score": a.get("sentiment_score", 0),
            "impact_score": _impact_to_numeric(a.get("impact_label", "low")),
        })
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["hour_ts", "article_count", "avg_sentiment", "avg_impact"])
    grouped = df.groupby("hour_ts").agg(
        article_count=("sentiment_score", "count"),
        avg_sentiment=("sentiment_score", "mean"),
        avg_impact=("impact_score", "mean"),
    ).reset_index()
    return grouped


def resample_returns_to_hourly(candles: list[dict]) -> pd.DataFrame:
    import pandas as pd
    df = pd.DataFrame(candles)
    if df.empty or "bar_ts" not in df.columns:
        return pd.DataFrame(columns=["hour_ts", "return"])
    df["hour_ts"] = (df["bar_ts"] // 3600) * 3600
    hourly = df.groupby("hour_ts").agg(
        open_price=("open", "first"),
        close_price=("close", "last"),
    ).reset_index()
    hourly["return"] = ((hourly["close_price"] - hourly["open_price"]) / hourly["open_price"].replace(0, np.nan)) * 100
    return hourly[["hour_ts", "return"]].dropna()


def compute_correlation(
    news_hourly: pd.DataFrame,
    returns_hourly: pd.DataFrame,
    n_bootstrap: int = 1000,
) -> dict[str, Any]:
    import pandas as pd
    merged = pd.merge(news_hourly, returns_hourly, on="hour_ts", how="inner")
    if len(merged) < 5:
        return {
            "news_return_corr": 0.0,
            "corr_p_value": 1.0,
            "corr_ci_lower": 0.0,
            "corr_ci_upper": 0.0,
            "sentiment_return_corr": 0.0,
            "news_volume_corr": 0.0,
            "sample_size": len(merged),
        }

    news_intensity = merged["article_count"].values
    returns = merged["return"].values
    sentiment = merged["avg_sentiment"].values

    news_return_corr, news_return_p = pearsonr(news_intensity, returns)
    sentiment_return_corr, _ = pearsonr(sentiment, returns)
    news_volume_corr, _ = pearsonr(news_intensity, np.abs(returns))

    corr_data = list(zip(news_intensity, returns))
    def _corr_stat(data, axis=0):
        arr = np.array(data)
        if arr.shape[0] < 2:
            return 0.0
        c, _ = pearsonr(arr[:, 0], arr[:, 1])
        return c

    try:
        boot = bootstrap(
            (corr_data,),
            _corr_stat,
            n_resamples=n_bootstrap,
            confidence_level=0.95,
            method="percentile",
        )
        ci_lower = boot.confidence_interval.low
        ci_upper = boot.confidence_interval.high
    except Exception:
        ci_lower = news_return_corr
        ci_upper = news_return_corr

    return {
        "news_return_corr": round(float(news_return_corr), 4),
        "corr_p_value": round(float(news_return_p), 6),
        "corr_ci_lower": round(float(ci_lower), 4),
        "corr_ci_upper": round(float(ci_upper), 4),
        "sentiment_return_corr": round(float(sentiment_return_corr), 4),
        "news_volume_corr": round(float(news_volume_corr), 4),
        "sample_size": len(merged),
    }


def compute_lag_analysis(
    news_hourly: pd.DataFrame,
    returns_hourly: pd.DataFrame,
    lags_minutes: list[int] | None = None,
) -> dict[str, Any]:
    import pandas as pd
    if lags_minutes is None:
        lags_minutes = [0, 15, 30, 60]
    returns_by_hour = returns_hourly.set_index("hour_ts")["return"]
    best_lag = 0
    best_corr = 0.0
    lag_results = {}
    for lag_min in lags_minutes:
        shifted = news_hourly.copy()
        shifted["hour_ts"] = ((shifted["hour_ts"] + lag_min * 60) // 3600) * 3600
        merged = pd.merge(shifted, returns_hourly, on="hour_ts", how="inner")
        if len(merged) < 3:
            continue
        corr, _ = pearsonr(merged["article_count"], merged["return"])
        lag_results[f"{lag_min}m"] = round(float(corr), 4)
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag_min
    return {
        "best_lag_minutes": best_lag,
        "best_lag_correlation": round(float(best_corr), 4),
        "lag_results": lag_results,
    }


def _impact_to_numeric(impact_label: str) -> float:
    mapping = {
        "high_bearish": -2.0,
        "high_bullish": 2.0,
        "medium": 1.0,
        "low": 0.0,
        "high": 1.5,
    }
    return mapping.get(impact_label, 0.0)
