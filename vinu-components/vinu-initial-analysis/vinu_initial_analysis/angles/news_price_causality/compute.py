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
from .regime_features import build_point_in_time_features
from vinu_initial_analysis.angles.signal_contract import tag_row

LOG = logging.getLogger(__name__)


def _compute_impact_rows(
    symbol: str,
    candles: list[dict],
    articles: list[dict],
    price_client: Any = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> list[dict]:
    """Per-article event study (impact labels, price changes, abnormal
    returns) plus the pre-event novelty/significance-classifier scores.
    Extracted from `compute()`'s former `time_format == "1min"` branch so
    the walk-forward-style backtest (backtest.py) can call it directly
    over the full real history, not just through the per-call `compute()`
    entry point — same external behavior, `compute()` below just calls
    this now. Returns a flat list of `type: "impact"` rows plus, if there
    was enough data to train, one `type: "significance_model_eval"` row.
    """
    from vinu_initial_analysis.angles._helpers import _compute_returns_series_indexed

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    if not articles or not candles:
        return rows

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

    # compute_impact_for_article() runs once per article (thousands of
    # articles per symbol over a multi-year backfill) against these same
    # candles_by_ticker/market_candles every time. Precomputing the
    # bar_ts index and market's indexed-returns ONCE here, instead of
    # inside that per-article call, turns an O(articles * total_bars)
    # blowup (confirmed to never finish for AAPL/TSLA's ~10k articles
    # over a 4.5-year 1-minute range) back into the O(log n) per-call
    # cost the bisect-based lookups were originally meant to have.
    ts_index_by_ticker = {
        t: [c.get("bar_ts", 0) for c in cands] for t, cands in candles_by_ticker.items()
    }
    market_returns_indexed = (
        _compute_returns_series_indexed(market_candles) if market_candles else None
    )

    for article in articles:
        events = compute_impact_for_article(
            article,
            price_client=price_client,
            candles_by_ticker=candles_by_ticker,
            market_candles=market_candles,
            ts_index_by_ticker=ts_index_by_ticker,
            market_returns_indexed=market_returns_indexed,
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

        scores, sample_labels, sig_eval = score_significance(
            impact_rows, articles_by_id,
            regime_features=build_point_in_time_features(candles, impact_rows),
        )
        for i, r in enumerate(impact_rows):
            if i in scores:
                r["significance_score"] = scores[i]
                r["significance_score_sample"] = sample_labels[i]
                tag_row(r, "significance_score")
        if sig_eval is not None:
            rows.append({
                "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
                "type": "significance_model_eval", **sig_eval,
            })

    return rows


def _compute_aggregate_tests(symbol: str, candles: list[dict], articles: list[dict]) -> list[dict]:
    """Granger causality + Pearson correlation + lag analysis, all on
    hourly-resampled news/returns — extracted from `compute()`'s former
    tail so the quarter-sliced backtest (backtest.py) can call this once
    per quarter, not just once over the whole history through `compute()`.
    Returns a flat list of `type: "granger"/"correlation"/"lag"` rows
    (0-3 rows, fewer if a test's own minimum-sample floor isn't met).
    """
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    if not articles or not candles:
        return rows

    news_hourly = resample_news_to_hourly(articles)
    returns_hourly = resample_returns_to_hourly(candles)
    if news_hourly.empty or returns_hourly.empty:
        return rows

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

    return rows


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

    # Per-article event study — driven by the highest-resolution bars
    # already fetched for this angle (1m, added to fix Bug-8:
    # price_change_5m/15m were unusable from 15m bars, which can't
    # resolve a 5-15 minute window) so it needs no per-article HTTP and no
    # separate cache. Run once, under the 1min pass, to avoid
    # triplicating rows.
    if time_format == "1min" and articles and candles:
        rows.extend(_compute_impact_rows(symbol, candles, articles, price_client, from_ts, to_ts))

    if not articles or not candles:
        if not any(r.get("type") == "impact" for r in rows):
            rows.append({
                "symbol": symbol, "analysis_at": now, "angle": "news_price_causality",
                "type": "status", "granger_causes_prices": False,
                "news_return_corr": 0.0, "best_lag_minutes": 0, "event_count": 0,
            })
        return pd.DataFrame(rows)

    rows.extend(_compute_aggregate_tests(symbol, candles, articles))

    return pd.DataFrame(rows) if rows else pd.DataFrame()



