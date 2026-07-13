from __future__ import annotations

import logging
from typing import Any

from vinu_correlation.clients.price_client import PriceClient
from vinu_correlation.engine.market_hours import (
    IMPACT_WINDOWS,
    classify_session,
    impact_window_within_session,
)
from vinu_correlation.engine.event_study import compute_abnormal_return, classify_significance

LOG = logging.getLogger(__name__)


def parse_tickers(tickers_raw: str | list) -> tuple[str, list[str]]:
    if isinstance(tickers_raw, str):
        import json
        try:
            tickers = json.loads(tickers_raw)
        except (json.JSONDecodeError, TypeError):
            tickers = [tickers_raw]
    else:
        tickers = list(tickers_raw) if tickers_raw else []
    if not tickers:
        return ("", [])
    return (tickers[0].upper(), [t.upper() for t in tickers[1:]])


def compute_impact_for_article(
    article: dict,
    price_client: PriceClient,
    windows: list[int] | None = None,
    session_aware: bool = True,
    impact_high_threshold: float = 2.0,
    impact_medium_threshold: float = 0.5,
) -> list[dict]:
    if windows is None:
        windows = list(IMPACT_WINDOWS.values())

    primary_ticker, secondary_tickers = parse_tickers(article.get("tickers", []))
    if not primary_ticker:
        return []

    ts = article.get("sort_ts", article.get("ts", 0))
    session = classify_session(ts).name if session_aware else "regular"

    all_tickers = [primary_ticker] + secondary_tickers
    weights = [1.0] + [0.5] * len(secondary_tickers)

    results = []
    for ticker, weight in zip(all_tickers, weights):
        max_window = max(windows) + 3600
        to_ts = ts + max_window
        candles = price_client.get_candles(ticker, from_ts=ts, to_ts=to_ts)

        price_changes: dict[str, float | None] = {}
        for win_name, win_sec in IMPACT_WINDOWS.items():
            if session_aware:
                frm, to = impact_window_within_session(ts, win_sec)
            else:
                frm, to = ts, ts + win_sec
            price_changes[win_name] = _compute_price_change(candles, frm, to)

        abnormal = compute_abnormal_return(candles, ts, window_sec=1800)
        sig_label = classify_significance(abnormal["ar_p_value"])

        impact_label = _classify_impact(
            article.get("sentiment", "NEUTRAL"),
            price_changes.get("30m", 0) or 0,
            impact_high_threshold,
            impact_medium_threshold,
        )

        event = {
            "article_id": article.get("id", ""),
            "symbol": ticker,
            "is_primary": ticker == primary_ticker,
            "ticker_count": len(all_tickers),
            "ts": ts,
            "session": session,
            "headline": article.get("headline", ""),
            "sentiment": article.get("sentiment", "NEUTRAL"),
            "sentiment_score": article.get("sentiment_score", 0),
            "impact_label": impact_label,
            "price_change_5m": price_changes.get("5m"),
            "price_change_15m": price_changes.get("15m"),
            "price_change_30m": price_changes.get("30m"),
            "price_change_1h": price_changes.get("1h"),
            "price_change_1d": price_changes.get("1d"),
            "abnormal_return_30m": abnormal["abnormal_return"],
            "car_1h": abnormal["car"],
            "ar_p_value": abnormal["ar_p_value"],
            "ar_significant": abnormal["significant"],
            "thread_id": article.get("thread_id", ""),
            "computed_at": int(__import__("time").time()),
        }
        results.append(event)

    return results


def _compute_price_change(candles: list[dict], from_ts: int, to_ts: int) -> float | None:
    filtered = [c for c in candles if from_ts <= c.get("bar_ts", 0) <= to_ts]
    if len(filtered) < 2:
        return None
    open_price = filtered[0].get("open", 0)
    close_price = filtered[-1].get("close", 0)
    if not open_price:
        return None
    return round((close_price - open_price) / open_price * 100, 4)


def _classify_impact(
    sentiment: str,
    price_change: float,
    high_threshold: float,
    medium_threshold: float,
) -> str:
    abs_change = abs(price_change)
    if abs_change >= high_threshold:
        if sentiment == "BEARISH":
            return "high_bearish"
        elif sentiment == "BULLISH":
            return "high_bullish"
        return "high"
    elif abs_change >= medium_threshold:
        return "medium"
    return "low"


def aggregate_by_thread(
    events: list[dict],
    min_thread_articles: int = 2,
) -> list[dict]:
    from collections import defaultdict
    threads: dict[str, list[dict]] = defaultdict(list)
    standalone = []
    for ev in events:
        tid = ev.get("thread_id", "")
        if tid:
            threads[tid].append(ev)
        else:
            standalone.append(ev)

    thread_summaries = []
    for tid, evs in threads.items():
        if len(evs) < min_thread_articles:
            standalone.extend(evs)
            continue
        sentiments = [e.get("sentiment_score", 0) for e in evs]
        cumulative = sum(sentiments) / len(sentiments) if sentiments else 0
        price_changes = [e.get("price_change_30m") or 0 for e in evs]
        max_change = max(price_changes, key=abs) if price_changes else 0
        timestamps = [e.get("ts", 0) for e in evs]
        time_span = max(timestamps) - min(timestamps) if timestamps else 0
        thread_summaries.append({
            "thread_id": tid,
            "lead_headline": evs[0].get("headline", ""),
            "article_count": len(evs),
            "cumulative_sentiment_score": round(cumulative, 2),
            "max_price_change": max_change,
            "time_span_seconds": time_span,
            "thread_intensity_score": round(len(evs) / max(time_span / 3600, 1), 2),
        })
    return {"threads": thread_summaries, "standalone": standalone}
