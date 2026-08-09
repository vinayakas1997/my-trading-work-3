"""peer_relative_strength's own backtest glue code.

Group B — one row already = one trading day's close-to-close computation,
no future bar to check a forecast against, so `run_walk_forward`'s
step/future contract doesn't apply. Two pieces, per the decided design
(04-enhancement-of-each-angle/21-peer_relative_strength.md SS5):

- `run_relative_strength_backtest`: the existing raw (symbol, peer,
  sampled date) rows `compute()` already produces, tagged with
  day-of-week/week/month/quarter only -- no session/subsession, since
  this angle produces exactly one row per trading day per peer, with no
  intraday variation to tag.
- `run_forward_return_validation`: the proposed enhancement -- joins each
  raw row to its own actual forward N-day return (5/10/20 trading days
  later), then aggregates Pearson correlation + bootstrapped CI per
  (peer, quarter) slice, reusing the shared `pearson_with_ci()` helper
  (same technique news_price_causality's correlation module uses).

No weights store, no naive baseline -- same reasoning as
news_price_causality: each forward-return correlation's own bootstrapped
CI (does it exclude 0) is already the "different from noise" check.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vinu_initial_analysis.angles._helpers import calendar_quarter_key, pearson_with_ci
from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.peer_relative_strength.compute import _aligned_closes, compute

FORWARD_DAYS = [5, 10, 20]

# The standard tagging rule includes session/subsession -- this angle has
# no intraday variation (one row per trading day per peer), so those two
# fields are dropped per the design doc's SS3/SS7 "no session/subsession
# tags" decision.
_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")


def run_relative_strength_backtest(
    symbol: str,
    bars: pd.DataFrame,
    price_client: Any = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> pd.DataFrame:
    df = compute(symbol, bars=bars, from_ts=from_ts, to_ts=to_ts, price_client=price_client)
    if df.empty or "bar_ts" not in df.columns:
        return df
    tags = df["bar_ts"].apply(lambda ts: {k: v for k, v in calendar_tag_row(int(ts)).items() if k in _DATE_ONLY_TAGS})
    tags_df = pd.DataFrame(list(tags))
    return pd.concat([df.reset_index(drop=True), tags_df.reset_index(drop=True)], axis=1)


def run_forward_return_validation(
    symbol: str,
    bars: pd.DataFrame,
    price_client: Any = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> pd.DataFrame:
    raw = compute(symbol, bars=bars, from_ts=from_ts, to_ts=to_ts, price_client=price_client)
    if raw.empty or "bar_ts" not in raw.columns or "relative_return_20d" not in raw.columns:
        return pd.DataFrame()

    aligned = _aligned_closes(symbol, bars, from_ts, to_ts, price_client)
    own = symbol.upper()
    if own not in aligned.columns:
        return pd.DataFrame()
    own_close = aligned[own].astype(float)

    # Forward N-day return anchored at each row's own date -- the actual
    # outcome that "did relative_return_20d/correlation predict anything"
    # is checked against. Computed once here (backtest-analysis time,
    # needs future data relative to each row), never fed back into the
    # real-time compute() path.
    forward_returns: dict[int, dict[int, float]] = {n: {} for n in FORWARD_DAYS}
    for n in FORWARD_DAYS:
        shifted = own_close.shift(-n)
        fwd = (shifted / own_close) - 1.0
        for idx, val in fwd.items():
            if pd.notna(val):
                forward_returns[n][int(idx.timestamp())] = float(val)

    raw = raw.dropna(subset=["relative_return_20d"]).copy()
    for n in FORWARD_DAYS:
        raw[f"forward_return_{n}d"] = raw["bar_ts"].map(forward_returns[n])
    raw["quarter_key"] = raw["bar_ts"].apply(lambda ts: calendar_quarter_key(int(ts)))

    rows: list[dict] = []
    for (peer, quarter), group in raw.groupby(["peer_symbol", "quarter_key"]):
        row: dict[str, Any] = {
            "symbol": symbol, "peer_symbol": peer, "quarter_key": quarter,
            "n_rows": int(len(group)),
        }
        for n in FORWARD_DAYS:
            g = group.dropna(subset=[f"forward_return_{n}d"])
            if len(g) < 5:
                continue
            result = pearson_with_ci(g["relative_return_20d"].to_numpy(), g[f"forward_return_{n}d"].to_numpy())
            row[f"forward_{n}d_corr"] = result["corr"]
            row[f"forward_{n}d_p_value"] = result["p_value"]
            row[f"forward_{n}d_ci_lower"] = result["ci_lower"]
            row[f"forward_{n}d_ci_upper"] = result["ci_upper"]
            row[f"forward_{n}d_sample_size"] = result["sample_size"]
        rows.append(row)

    return pd.DataFrame(rows)
