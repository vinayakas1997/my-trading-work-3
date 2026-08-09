"""shock_personality's own backtest glue code -- the new Layer 1 output
per the design doc (04-enhancement-of-each-angle/25-shock_personality.md
SS4/SS5): one tagged row per detected shock (gap or vol-spike), carrying
type/magnitude/z_score/has_news/nearest_news_days -- previously computed
by `_cross_reference_news` and then thrown away (Bug #3, see compute.py's
module docstring).

Tagging differs by trigger type/timeframe, per the design's explicit
rule: gap-shock rows always get day-of-week/week/month/quarter only (a
gap is inherently a session-boundary event, tagging it with a session id
isn't meaningful); vol-spike rows get the full standard tagging
(including session/subsession) on intraday timeframes, date-only at 1D.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.shock_personality.compute import MIN_OBSERVATIONS, _tag_shocks

_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")
_INTRADAY_TIMEFRAMES = ("1min", "5min", "15min", "1H", "4H")


def run_shock_backtest(
    symbol: str,
    bars: pd.DataFrame,
    news: list[dict] | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    if bars is None or bars.empty or len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame()

    shocks = _tag_shocks(bars, news)
    full_tagging = time_format in _INTRADAY_TIMEFRAMES

    rows: list[dict] = []
    for s in shocks:
        bar_ts = int(s["date"])
        row = {
            "symbol": symbol,
            "bar_ts": bar_ts,
            "type": s["type"],
            "magnitude": s["magnitude"],
            "z_score": s["z_score"],
            "has_news": s.get("has_news", False),
            "nearest_news_days": s.get("nearest_news_days"),
        }
        tags = calendar_tag_row(bar_ts)
        if s["type"] == "gap" or not full_tagging:
            tags = {k: v for k, v in tags.items() if k in _DATE_ONLY_TAGS}
        row.update(tags)
        rows.append(row)

    return pd.DataFrame(rows)
