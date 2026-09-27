"""Search Trends — Google search interest over time for a symbol's ticker.

High-expectations cross-check (system-wide-audit-and-design,
high-expectations/chatgpt-version docs): "alternative data ... search
trends" was a named senior-quant expectation with no existing ingestion
anywhere in this system. This is that first, real version.

Deliberately queries the raw ticker symbol, not a resolved company name:
no symbol-to-company-name mapping exists anywhere in this codebase to
reuse, and building one is a separate, real scope decision, not silently
invented here. This is a real, known limitation for tickers that are
also common English words or otherwise ambiguous as a bare search term
(e.g. a single-letter symbol) — left open rather than papered over.

Uses `pytrends` (the unofficial Google Trends API — no paid tier or API
key needed, unlike the order-book/on-chain alt-data candidates checked
alongside this one and explicitly deferred instead). Google Trends has
no formal API and rate-limits aggressively; every failure mode here
fails open to a `no_data` status row, the same posture every other
external-data fetch in this codebase already uses (news/price/options/
correlation all degrade the same way on a fetch failure) — this is a
real, expected outcome for this data source, not a bug to suppress.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

# pytrends' own relative-window syntax. 12 months at weekly resolution
# (pytrends' own granularity choice for a window this long, not
# something this module controls) gives ~52 samples — enough for the
# rolling z-score below to mean something.
TIMEFRAME = "today 12-m"
GEO = ""  # worldwide; a per-market override is a real, separate decision
ROLLING_BASELINE_WEEKS = 12


def _empty_result(symbol: str, status: str, **extra: Any) -> pd.DataFrame:
    row: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": datetime.now(timezone.utc).isoformat(),
        "angle": "search_trends",
        "status": status,
    }
    row.update(extra)
    return pd.DataFrame([row])


def _fetch_interest_over_time(symbol: str) -> pd.DataFrame | None:
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return None
    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        pytrends.build_payload([symbol.upper()], cat=0, timeframe=TIMEFRAME, geo=GEO, gprop="")
        df = pytrends.interest_over_time()
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    df = _fetch_interest_over_time(symbol)
    if df is None:
        return _empty_result(symbol, "no_data")

    keyword_col = symbol.upper()
    if keyword_col not in df.columns:
        return _empty_result(symbol, "no_data")

    analysis_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        value = row[keyword_col]
        if pd.isna(value):
            continue
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "search_trends",
            "date": idx.strftime("%Y-%m-%d"),
            "bar_ts": int(idx.timestamp()),
            "search_interest": int(value),
            "is_partial": bool(row.get("isPartial", False)),
        })

    if not rows:
        return _empty_result(symbol, "no_data")

    result = pd.DataFrame(rows)
    # Google's 0-100 scale is already relative to the requested window,
    # not an absolute count -- a genuine spike is one relative to this
    # series' own recent baseline, not every value above some arbitrary
    # constant. min_periods=4 so the first month of a fresh series still
    # gets a (noisier) score rather than staying NaN for 12 whole weeks.
    interest = result["search_interest"]
    rolling_mean = interest.rolling(ROLLING_BASELINE_WEEKS, min_periods=4).mean()
    rolling_std = interest.rolling(ROLLING_BASELINE_WEEKS, min_periods=4).std()
    result["search_interest_zscore"] = (interest - rolling_mean) / rolling_std
    return result
