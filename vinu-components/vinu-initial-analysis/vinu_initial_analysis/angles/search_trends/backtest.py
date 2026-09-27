"""search_trends' own backtest glue code -- tags each sampled week with
calendar info and joins to the symbol's own actual forward return, so
"does a search-interest spike predict anything" has a real, checkable
answer instead of just a recorded number. Same forward-return-plus-
bootstrapped-CI technique peer_relative_strength's own forward-return
validation already established (`pearson_with_ci`), reused rather than
reinvented.

Weekly resolution, no session/subsession tagging -- same reasoning as
peer_relative_strength/shock_clustering (no intraday dimension to tag).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vinu_initial_analysis.angles._helpers import calendar_quarter_key, pearson_with_ci
from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.search_trends.compute import compute

FORWARD_DAYS = [5, 10, 20]
_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")


def _daily_close_series(bars: pd.DataFrame) -> pd.Series | None:
    if bars is None or bars.empty or "close" not in bars.columns or "bar_ts" not in bars.columns:
        return None
    ts = pd.to_numeric(bars["bar_ts"], errors="coerce").dropna().astype("int64")
    idx = pd.to_datetime(ts.to_numpy(), unit="s").tz_localize("UTC")
    out = pd.Series(bars["close"].astype(float).values, index=idx).sort_index()
    return out.groupby(out.index).last()


def run_search_trends_backtest(symbol: str, bars: pd.DataFrame) -> pd.DataFrame:
    """Real forward-return validation: for each sampled week's search
    interest, does the trailing z-score correlate with the symbol's own
    actual forward N-day return? `bars` supplies the real close series
    the forward return is measured against -- compute() itself never
    needs bars (it fetches Google Trends data independently of price
    history), only this backtest join does."""
    raw = compute(symbol)
    if raw.empty or "bar_ts" not in raw.columns or "search_interest_zscore" not in raw.columns:
        return pd.DataFrame()

    close = _daily_close_series(bars)
    if close is None or close.empty:
        return pd.DataFrame()

    raw = raw.dropna(subset=["search_interest_zscore"]).copy()
    if raw.empty:
        return pd.DataFrame()

    fwd = pd.DataFrame({"date": close.index})
    for n in FORWARD_DAYS:
        shifted = close.shift(-n)
        fwd[f"forward_return_{n}d"] = ((shifted / close) - 1.0).to_numpy()

    # Built from `bar_ts` (int seconds), not by re-parsing the `date`
    # string column -- must match `close.index`'s own dtype exactly
    # (`_daily_close_series` builds it the same way) or merge_asof raises
    # on a resolution mismatch (e.g. datetime64[us] vs datetime64[s]).
    raw["date_dt"] = pd.to_datetime(raw["bar_ts"].astype("int64"), unit="s", utc=True)
    raw = raw.sort_values("date_dt")
    fwd = fwd.sort_values("date")

    # Each week's search-interest sample is matched to the closest real
    # close AT OR AFTER that date (`direction="forward"`) -- a
    # search-interest week can never be validated against a return
    # measured before the sample itself was even known, matching this
    # whole codebase's own point-in-time-safety discipline.
    merged = pd.merge_asof(raw, fwd, left_on="date_dt", right_on="date", direction="forward")

    merged["quarter_key"] = merged["bar_ts"].apply(lambda ts: calendar_quarter_key(int(ts)))
    for col in _DATE_ONLY_TAGS:
        merged[col] = merged["bar_ts"].apply(lambda ts, col=col: calendar_tag_row(int(ts)).get(col))
    raw = merged

    rows: list[dict[str, Any]] = []
    for quarter, group in raw.groupby("quarter_key"):
        row: dict[str, Any] = {"symbol": symbol, "quarter_key": quarter, "n_rows": int(len(group))}
        for n in FORWARD_DAYS:
            g = group.dropna(subset=[f"forward_return_{n}d"])
            if len(g) < 5:
                continue
            result = pearson_with_ci(
                g["search_interest_zscore"].to_numpy(), g[f"forward_return_{n}d"].to_numpy(),
            )
            row[f"forward_{n}d_corr"] = result["corr"]
            row[f"forward_{n}d_p_value"] = result["p_value"]
            row[f"forward_{n}d_ci_lower"] = result["ci_lower"]
            row[f"forward_{n}d_ci_upper"] = result["ci_upper"]
            row[f"forward_{n}d_sample_size"] = result["sample_size"]
        rows.append(row)

    return pd.DataFrame(rows)
