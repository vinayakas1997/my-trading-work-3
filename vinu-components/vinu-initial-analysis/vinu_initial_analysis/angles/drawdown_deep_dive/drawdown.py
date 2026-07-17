from __future__ import annotations

from typing import Any


_SENTIMENT_WEIGHTS: dict[str, float] = {
    "BULLISH": 1.0,
    "BEARISH": 1.0,
    "NEUTRAL": 0.3,
}


def get_drawdowns(
    symbol: str,
    candles: list[dict],
    from_ts: int | None = None,
    to_ts: int | None = None,
    drop_threshold_pct: float = -3.0,
    lookback_hours: int = 24,
) -> list[dict[str, Any]]:
    sorted_c = sorted(
        [c for c in candles
         if (from_ts is None or c.get("bar_ts", 0) >= from_ts)
         and (to_ts is None or c.get("bar_ts", 0) <= to_ts)],
        key=lambda x: x.get("bar_ts", 0),
    )
    if len(sorted_c) < 2:
        return []

    peaks: list[dict] = []
    i = 0
    while i < len(sorted_c):
        if i == 0 or sorted_c[i].get("high", 0) >= sorted_c[i - 1].get("high", 0):
            peak_price = sorted_c[i].get("high", 0)
            if not peaks or peak_price > peaks[-1]["price"]:
                peaks.append({"index": i, "ts": sorted_c[i]["bar_ts"], "price": peak_price})
        i += 1

    drawdowns = []
    for peak in peaks:
        peak_idx = peak["index"]
        trough_idx = peak_idx + 1
        while trough_idx < len(sorted_c):
            drop = (sorted_c[trough_idx].get("close", 0) - peak["price"]) / peak["price"] * 100
            if drop <= drop_threshold_pct:
                ts_lookback = peak["ts"] - lookback_hours * 3600
                drawdowns.append({
                    "symbol": symbol,
                    "peak_ts": peak["ts"],
                    "trough_ts": sorted_c[trough_idx]["bar_ts"],
                    "drop_pct": round(drop, 2),
                    "peak_price": peak["price"],
                    "trough_price": sorted_c[trough_idx]["close"],
                    "lookback_from_ts": ts_lookback,
                })
                break
            trough_idx += 1

    return drawdowns


def _compute_event_weight(event: dict) -> float:
    score = abs(event.get("price_change_30m", 0) or 0)
    sentiment = event.get("sentiment", "NEUTRAL").upper()
    weight = _SENTIMENT_WEIGHTS.get(sentiment, 0.3)
    return score * weight


def attribute_drawdown(
    symbol: str,
    peak_ts: int,
    trough_ts: int,
    events: list[dict],
    market_returns: list[dict] | None = None,
) -> dict[str, Any]:
    from vinu_initial_analysis.angles.session_time_analysis.market_hours import IMPACT_WINDOWS

    relevant_events = [
        e for e in events
        if e.get("symbol", "").upper() == symbol.upper()
        and e.get("ts", 0) <= peak_ts
    ]

    n_events = len(relevant_events)
    if n_events == 0:
        return {
            "peak_ts": peak_ts,
            "trough_ts": trough_ts,
            "drop_pct": 0.0,
            "attribution": {
                "news_driven_pct": 0.0,
                "market_beta_pct": 0.0,
                "unexplained_pct": 1.0,
                "contributing_events": [],
            },
        }

    total_weighted_score = sum(_compute_event_weight(ev) for ev in relevant_events)

    contributing = []
    for ev in relevant_events:
        w = _compute_event_weight(ev)
        contributing.append({
            "headline": ev.get("headline", ""),
            "attribution_pct": round(w / total_weighted_score, 4) if total_weighted_score > 0 else 0.0,
            "sentiment": ev.get("sentiment", "NEUTRAL"),
            "impact_label": ev.get("impact_label", "low"),
        })

    baseline_score = 0.1 * n_events  # normalize by event count
    news_pct = total_weighted_score / (total_weighted_score + baseline_score + 1.0)
    news_pct = min(news_pct, 0.95)
    market_pct = 0.0 if market_returns is None else 0.2
    unexplained_pct = 1.0 - news_pct - market_pct

    return {
        "peak_ts": peak_ts,
        "trough_ts": trough_ts,
        "drop_pct": 0.0,
        "attribution": {
            "news_driven_pct": round(news_pct, 4),
            "market_beta_pct": round(market_pct, 4),
            "unexplained_pct": round(max(unexplained_pct, 0), 4),
            "contributing_events": sorted(contributing, key=lambda x: x["attribution_pct"], reverse=True),
        },
    }
