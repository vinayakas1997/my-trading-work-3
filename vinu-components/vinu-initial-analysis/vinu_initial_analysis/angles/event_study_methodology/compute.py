"""Event Study Methodology — abnormal returns, CAR, t-test significance around news events."""

import pandas as pd
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import bars_to_candle_list
from .event_study import compute_abnormal_return, classify_significance


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    candles = bars_to_candle_list(bars)
    articles = news or []
    rows: list[dict] = []

    if not candles or not articles:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "event_study_methodology",
            "type": "status", "events_analyzed": 0,
        })
        return pd.DataFrame(rows)

    # Compute abnormal return for each news event
    for article in articles:
        ts = article.get("sort_ts", article.get("ts", 0))
        if not ts:
            continue
        ar = compute_abnormal_return(candles, ts, window_sec=1800)
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "event_study_methodology",
            "type": "event",
            "article_id": article.get("id", ""),
            "headline": article.get("headline", "")[:120],
            "event_ts": ts,
            "abnormal_return": ar["abnormal_return"],
            "car": ar["car"],
            "ar_p_value": ar["ar_p_value"],
            "significant": ar["significant"],
            "expected_return": ar["expected_return"],
            "significance_label": classify_significance(ar["ar_p_value"]),
        })

    # Summary
    total = len(rows)
    significant_count = sum(1 for r in rows if r.get("significant"))
    avg_ar = sum(r.get("abnormal_return", 0.0) for r in rows) / total if total else 0.0
    rows.append({
        "symbol": symbol, "analysis_at": now, "angle": "event_study_methodology",
        "type": "summary",
        "events_analyzed": total,
        "significant_events": significant_count,
        "avg_abnormal_return": round(avg_ar, 6),
    })

    return pd.DataFrame(rows) if rows else pd.DataFrame()



