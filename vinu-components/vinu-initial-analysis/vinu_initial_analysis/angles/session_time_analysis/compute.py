"""Session / Time-of-Day Analysis — session classification, news gaps, transition gaps, premarket gap."""

import pandas as pd
from datetime import datetime, timezone

from .market_hours import classify_session, get_session_boundaries
from .blocks import compute_time_gaps, compute_correlation_by_session, compute_premarket_gap


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

    if not articles:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "session_time_analysis",
            "type": "gap", "gap_hours": None, "last_article_ts": None, "last_headline": None,
        })
        return pd.DataFrame(rows)

    # Premarket gap
    gap = compute_premarket_gap(articles)
    rows.append({
        "symbol": symbol, "analysis_at": now, "angle": "session_time_analysis",
        "type": "premarket_gap",
        "gap_hours": gap.get("gap_hours"),
        "last_article_ts": gap.get("last_article_ts"),
        "last_headline": gap.get("last_headline", ""),
        "session": gap.get("session", ""),
    })

    # Time gaps between consecutive articles
    time_gaps = compute_time_gaps(articles)
    if time_gaps:
        avg_gap = sum(g["gap_hours"] for g in time_gaps) / len(time_gaps)
        max_gap = max(g["gap_hours"] for g in time_gaps)
    else:
        avg_gap = max_gap = 0.0
    rows.append({
        "symbol": symbol, "analysis_at": now, "angle": "session_time_analysis",
        "type": "time_gap_summary",
        "total_gaps": len(time_gaps),
        "avg_gap_hours": round(avg_gap, 4),
        "max_gap_hours": round(max_gap, 4),
    })

    # Session boundaries info
    ref_ts = from_ts or (to_ts or int(datetime.now(timezone.utc).timestamp()))
    sessions = get_session_boundaries(ref_ts)
    for s in sessions:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "session_time_analysis",
            "type": "session_boundary",
            "session_name": s.name,
            "utc_start_hour": s.utc_start_hour,
            "utc_end_hour": s.utc_end_hour,
        })

    # Correlation by session (needs candles too)
    if candles:
        by_session = compute_correlation_by_session(articles, candles)
        for sname, corr_data in by_session.items():
            rows.append({
                "symbol": symbol, "analysis_at": now, "angle": "session_time_analysis",
                "type": "session_correlation",
                "session_name": sname,
                "pearson": corr_data["pearson"],
                "p_value": corr_data["p_value"],
                "sample_hours": corr_data["sample_hours"],
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _bars_to_candle_list(bars: pd.DataFrame | None) -> list[dict]:
    if bars is None or bars.empty:
        return []
    if "bar_ts" not in bars.columns:
        return []
    return bars.to_dict("records")
