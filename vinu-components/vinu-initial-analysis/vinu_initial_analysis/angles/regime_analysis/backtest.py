"""regime_analysis's own backtest glue code -- the two new outputs the
design doc proposes on top of compute()'s existing (now leak-fixed)
whole-history summary (04-enhancement-of-each-angle/23-regime_analysis.md
SS3/SS5):

- `run_per_bar_regime_backtest`: one row per classified bar (Layer 1,
  new -- the current code only ever emits one aggregated row per regime
  across the ENTIRE requested range, so "was Q1 2023 mostly bull or
  bear" isn't answerable today). Tagged day-of-week/week/month/quarter
  only -- no session/subsession, same reasoning as peer_relative_strength
  (this is daily+ granularity regime labeling, not an intraday signal).
- `run_quarterly_regime_breakdown`: per-(symbol, quarter, regime) counts
  + pct_of_time_in_quarter, closing the actual time-sliced-visibility gap
  the per-bar rows alone don't answer on their own (a consumer would
  otherwise have to re-derive quarter buckets from the raw rows every
  time).

No weights store, no naive baseline -- not a forecaster.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._helpers import calendar_quarter_key
from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.regime_analysis.compute import MIN_OBSERVATIONS, _compute_regime_frame

_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")


def run_per_bar_regime_backtest(
    symbol: str,
    bars: pd.DataFrame,
    time_format: str | None = None,
) -> pd.DataFrame:
    if bars is None or len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame()

    rf = _compute_regime_frame(bars, time_format)
    if rf.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, r in rf.iterrows():
        bar_ts = int(r["bar_ts"])
        row = {
            "symbol": symbol,
            "bar_ts": bar_ts,
            "regime": r["regime"],
            "ret_20d": float(r["ret_20d"]),
            "vol_21d": float(r["vol"]),
            "vol_trailing_z": float(r["vol_trailing_z"]),
        }
        row.update({k: v for k, v in calendar_tag_row(bar_ts).items() if k in _DATE_ONLY_TAGS})
        rows.append(row)

    return pd.DataFrame(rows)


def run_quarterly_regime_breakdown(
    symbol: str,
    bars: pd.DataFrame,
    time_format: str | None = None,
) -> pd.DataFrame:
    per_bar = run_per_bar_regime_backtest(symbol, bars, time_format)
    if per_bar.empty:
        return pd.DataFrame()

    per_bar["quarter_key"] = per_bar["bar_ts"].apply(lambda ts: calendar_quarter_key(int(ts)))

    rows: list[dict] = []
    for quarter, q_group in per_bar.groupby("quarter_key"):
        total = len(q_group)
        for regime, r_group in q_group.groupby("regime"):
            rows.append({
                "symbol": symbol,
                "quarter_key": quarter,
                "regime": regime,
                "count": int(len(r_group)),
                "pct_of_time_in_quarter": float(len(r_group) / total),
            })

    return pd.DataFrame(rows)
