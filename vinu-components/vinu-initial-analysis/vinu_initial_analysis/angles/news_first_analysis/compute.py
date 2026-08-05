"""News First Analysis — sentiment distribution, session baselines, priority scoring.

DEPRECATED, not deleted: per
New-talk-/Final-implementation/03-actual-plan-findings/05-angle-reconciliation.md
("Redundant"), this angle's ground (categorization, sentiment, event/
priority scoring) is now covered by vinu-news's own Section-1 methods
(vinu-news/vinu_news/analysis/methods/ — event_type_classification,
vader_finance_tuned_sentiment, and vinu-news's pre-existing FinBERT/NER/
category pipeline), which is where the reconciliation doc recommends
this kind of news analysis live going forward, not duplicated here a
third time. Left in place rather than removed — still correct, still
tested, and deleting a working feature is a bigger decision than this
pass is scoped to make unilaterally. Treat this as legacy/superseded;
removing it outright is a follow-up decision, not done here.
"""

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
