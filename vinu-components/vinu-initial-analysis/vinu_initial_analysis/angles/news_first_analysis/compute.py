"""News First Analysis — sentiment distribution, session baselines, priority scoring."""

import pandas as pd
from datetime import datetime, timezone

from .baseline import compute_baseline


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
    rows: list[dict] = []

    if not articles:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "news_first_analysis",
            "session": "", "article_count": 0, "mean": 0.0, "stddev": 0.0,
            "z_score": 0.0, "deviation_level": "no_data",
        })
        return pd.DataFrame(rows)

    baselines = compute_baseline(articles, window_days=7, session_aware=True)
    for bl in baselines:
        bl["symbol"] = symbol
        bl["analysis_at"] = now
        bl["angle"] = "news_first_analysis"
        rows.append(bl)

    return pd.DataFrame(rows) if rows else pd.DataFrame()
