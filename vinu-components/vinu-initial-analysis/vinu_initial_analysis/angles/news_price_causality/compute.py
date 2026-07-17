"""News-Price Causality — Granger, Pearson correlation, lag analysis, impact scoring."""

import pandas as pd
from datetime import datetime, timezone

from .impact import compute_impact_for_article, aggregate_by_thread
from .correlation import (
    compute_correlation, compute_lag_analysis,
    resample_news_to_hourly, resample_returns_to_hourly,
)
from .granger import run_granger_causality_test


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    articles = news or []
    candles = _bars_to_candle_list(bars)
    rows: list[dict] = []

    if not articles or not candles:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
            "type": "status", "granger_causes_prices": False,
            "news_return_corr": 0.0, "best_lag_minutes": 0, "event_count": 0,
        })
        return pd.DataFrame(rows)

    # Granger causality
    news_hourly = resample_news_to_hourly(articles)
    returns_hourly = resample_returns_to_hourly(candles)
    if not news_hourly.empty and not returns_hourly.empty:
        merged = pd.merge(news_hourly, returns_hourly, on="hour_ts", how="inner")
        if len(merged) >= 12:
            g = run_granger_causality_test(merged["article_count"], merged["return"], max_lag=12)
            rows.append({
                "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
                "type": "granger",
                "granger_causes_prices": g["granger_causes_prices"],
                "best_lag_minutes": g["best_lag_minutes"],
                "p_value": g["p_value"],
                "sample_size": len(merged),
            })

        # Pearson correlation
        c = compute_correlation(news_hourly, returns_hourly, n_bootstrap=500)
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
            "type": "correlation",
            "news_return_corr": c["news_return_corr"],
            "corr_p_value": c["corr_p_value"],
            "sentiment_return_corr": c["sentiment_return_corr"],
            "news_volume_corr": c["news_volume_corr"],
            "sample_size": c["sample_size"],
        })

        # Lag analysis
        lag = compute_lag_analysis(news_hourly, returns_hourly, lags_minutes=[0, 15, 30, 60, 120])
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
            "type": "lag",
            "best_lag_minutes": lag["best_lag_minutes"],
            "best_lag_correlation": lag["best_lag_correlation"],
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _bars_to_candle_list(bars: pd.DataFrame | None) -> list[dict]:
    if bars is None or bars.empty:
        return []
    cols = bars.columns.tolist()
    if "bar_ts" not in cols:
        return []
    return bars.to_dict("records")
