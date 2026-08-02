"""News-Price Causality — Granger, Pearson correlation, lag analysis, impact scoring."""

import logging
from typing import Any

import pandas as pd
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import bars_to_candle_list
from .impact import compute_impact_for_article, aggregate_by_thread
from .correlation import (
    compute_correlation, compute_lag_analysis,
    resample_news_to_hourly, resample_returns_to_hourly,
)
from .granger import run_granger_causality_test
from .novelty import compute_novelty_scores
from .significance_model import score_significance

LOG = logging.getLogger(__name__)


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
    price_client: Any = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    articles = news or []
    candles = bars_to_candle_list(bars)
    rows: list[dict] = []

    # Per-article event study (impact labels, price changes, abnormal
    # returns) — driven by the highest-resolution bars already fetched for
    # this angle (1m, added to fix Bug-8: price_change_5m/15m were unusable
    # from 15m bars, which can't resolve a 5-15 minute window) so it needs
    # no per-article HTTP and no separate cache. Run once, under the 1min
    # pass, to avoid triplicating rows.
    if time_format == "1min" and articles and candles:
        from .impact import compute_impact_for_article

        candles_by_ticker = {symbol: sorted(candles, key=lambda c: c.get("bar_ts", 0))}

        # Market-factor control: fit abnormal returns against SPY instead of
        # the stock's own historical mean, so a market-wide move (e.g. a Fed
        # announcement) doesn't get misattributed to whatever news article
        # happens to land in the same window. Best-effort — if SPY isn't
        # backfilled or the fetch fails, compute_abnormal_return() falls
        # back to the mean-adjusted model automatically (market_candles=None).
        market_candles: list[dict] | None = None
        if price_client is not None and symbol != "SPY":
            try:
                spy = price_client.get_candles(
                    "SPY", from_ts=from_ts, to_ts=to_ts, interval="1min",
                )
                if spy:
                    market_candles = sorted(spy, key=lambda c: c.get("bar_ts", 0))
            except Exception:
                LOG.warning("SPY fetch failed for market-model abnormal returns; falling back to mean-adjusted model", exc_info=True)

        for article in articles:
            events = compute_impact_for_article(
                article,
                price_client=price_client,
                candles_by_ticker=candles_by_ticker,
                market_candles=market_candles,
            )
            for ev in events:
                ev.setdefault("symbol", symbol)
                ev["analysis_at"] = now
                ev["angle"] = "news_price_causality"
                rows.append(ev)

        # Novelty score + significance classifier — both are pre-event
        # features (computable the instant the article lands, unlike
        # ar_significant which needs the post-event price window). See
        # novelty.py and significance_model.py docstrings for what these
        # scores mean and how to use them; this is deliberately the only
        # place they're wired in, so future changes to the feature set
        # only need to happen in those two modules.
        impact_rows = [r for r in rows if r.get("type") == "impact"]
        if impact_rows:
            novelty_map = compute_novelty_scores(articles)
            articles_by_id = {a.get("id"): a for a in articles}
            for r in impact_rows:
                r["novelty_score"] = novelty_map.get(r.get("article_id"), 1.0)

            scores, sample_labels, sig_eval = score_significance(impact_rows, articles_by_id)
            for i, r in enumerate(impact_rows):
                if i in scores:
                    r["significance_score"] = scores[i]
                    r["significance_score_sample"] = sample_labels[i]
            if sig_eval is not None:
                rows.append({
                    "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
                    "type": "significance_model_eval", **sig_eval,
                })

    if not articles or not candles:
        if not any(r.get("type") == "impact" for r in rows):
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



