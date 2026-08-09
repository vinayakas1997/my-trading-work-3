"""shock_clustering's own backtest glue code -- the new Layer 1 output
per the design doc (04-enhancement-of-each-angle/24-shock_clustering.md
SS4/SS5): one tagged row per detected shock date, closing the gap that
`compute()`'s own output only ever returns the first 10 shock dates as a
plain list with no way to slice by calendar period.

Tagged day-of-week/week/month/quarter only -- no session/subsession,
same reasoning as peer_relative_strength/regime_analysis (shock
detection is a daily-bar concept, no intraday dimension to tag).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.shock_clustering.compute import MIN_OBSERVATIONS, _detect_shocks

_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")


def run_shock_date_backtest(symbol: str, bars: pd.DataFrame) -> pd.DataFrame:
    if bars is None or bars.empty or len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame()

    shocks = _detect_shocks(bars)
    rows: list[dict] = []
    for s in shocks:
        row = {
            "symbol": symbol,
            "bar_ts": s["bar_ts"],
            "date": s["date"],
            "trigger": s["trigger"],
            "z": s["z"],
        }
        row.update({k: v for k, v in calendar_tag_row(s["bar_ts"]).items() if k in _DATE_ONLY_TAGS})
        rows.append(row)

    return pd.DataFrame(rows)
