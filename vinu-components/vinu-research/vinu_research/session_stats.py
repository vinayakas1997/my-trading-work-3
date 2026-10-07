"""Which hours of the day a strategy earns its money in, and how much risk to take in each.

Input is the strategy's own bar-by-bar returns from a backtest over ALL sessions (the simulator's equity curve). Each return is
attributed to the session its bar opened in (vinu_infra.sessions). Output feeds two decisions:

  * `trading_sessions`: the sessions the strategy is approved to trade (a session needs enough bars to judge and a positive
    result; no evidence means NOT approved: the system does not trade hours it has not measured);
  * `size_multiplier` per session, the risk-management hint: outside regular hours spreads are wider and prices jump, so a
    session whose return volatility is higher than the regular session's is traded smaller, in proportion.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from vinu_infra.sessions import REGULAR, TRADABLE_SESSIONS, session_mask

#: Fewest bars a session needs before it is judged at all (below it: `insufficient_data`, not traded).
MIN_BARS_PER_SESSION = 200
MIN_MULTIPLIER = 0.25
#: A bar whose gap from the previous bar is more than this many times the usual bar spacing carries the move of the gap (a
#: weekend, a closed hour, a session the data source barely covers), not the move of its own interval. Those returns are
#: not credited to the session of the bar that happens to come next (problem log O13).
GAP_FACTOR = 2.0
#: A session's bars per day must reach this share of what the regular session's bar density implies for its length. IEX
#: shows about 2 bars a day in pre-market against about 7 in the regular session: far under, so it cannot be judged.
MIN_DENSITY = 0.5
#: Minutes in each tradable session (vinu_infra.sessions), used to scale the regular session's bar density.
SESSION_MINUTES = {"premarket": 330, "regular": 390, "afterhours": 240, "overnight": 480}


def session_breakdown(returns: pd.Series, *, periods_per_year: float = 252.0) -> dict[str, dict[str, Any]]:
    """Per session: bars, total return (compounded), mean and volatility of the bar return, annualised Sharpe, the share of
    the strategy's summed return that came from it. `returns` is indexed by naive UTC bar-open times."""
    if returns is None or len(returns) == 0:
        return {}
    idx = pd.DatetimeIndex(returns.index)
    utc = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    stamps = pd.Index((utc - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1))      # unit-independent
    values = returns.to_numpy(dtype=float)
    total = float(values.sum())
    seconds = stamps.to_numpy(dtype=float)
    order = np.argsort(seconds, kind="stable")
    gaps = np.diff(seconds[order], prepend=seconds[order][0])
    usual = float(np.median(gaps[gaps > 0])) if (gaps > 0).any() else 0.0
    after_gap = np.zeros(len(values), dtype=bool)
    if usual > 0:
        after_gap[order] = gaps > GAP_FACTOR * usual
    days = max(1, pd.DatetimeIndex(utc.tz_convert("America/New_York").tz_localize(None).normalize()).nunique())
    out: dict[str, dict[str, Any]] = {}
    for name in TRADABLE_SESSIONS:
        in_session = session_mask(stamps.to_numpy(), frozenset({name}))
        m = in_session & ~after_gap
        r = values[m]
        bars = int(m.sum())
        vol = float(r.std(ddof=1)) if bars > 1 else 0.0
        mean = float(r.mean()) if bars else 0.0
        out[name] = {
            "bars": int(in_session.sum()),                  # every bar that opened in the session
            "valid_bars": bars,                             # those not carrying a gap: what the statistics below use
            "gap_bars": int((in_session & after_gap).sum()),
            "bars_per_day": bars / days,
            "total_return": float(np.prod(1.0 + r) - 1.0) if bars else 0.0,
            "mean": mean,
            "volatility": vol,
            "sharpe": (mean / vol * math.sqrt(periods_per_year)) if vol > 0 else 0.0,
            "share_of_return": (float(r.sum()) / total) if total else 0.0,
            "traded_bars": int((r != 0).sum()),
        }
    return out


def risk_hints(breakdown: dict[str, dict[str, Any]], *, min_bars: int = MIN_BARS_PER_SESSION) -> dict[str, dict[str, Any]]:
    """Per session: verdict (`trade` | `reduce` | `avoid` | `insufficient_data`), a position-size multiplier in [0, 1] and why."""
    reg = breakdown.get(REGULAR) or {}
    base_vol = reg.get("volatility") or 0.0
    reg_density = reg.get("bars_per_day") or 0.0
    hints: dict[str, dict[str, Any]] = {}
    for name in TRADABLE_SESSIONS:
        s = breakdown.get(name) or {}
        bars, traded = int(s.get("valid_bars", s.get("bars", 0))), int(s.get("traded_bars", 0))
        if bars < min_bars or traded < min_bars // 4:
            hints[name] = {"verdict": "insufficient_data", "size_multiplier": 0.0,
                           "reason": f"{bars} bars ({traded} with a position); at least {min_bars} bars are needed to judge a session"}
            continue
        if name != REGULAR and reg_density:
            expected = reg_density * SESSION_MINUTES[name] / SESSION_MINUTES[REGULAR]
            if s.get("bars_per_day", 0.0) < MIN_DENSITY * expected:
                hints[name] = {"verdict": "insufficient_data", "size_multiplier": 0.0,
                               "reason": f"{s.get('bars_per_day', 0.0):.1f} bars a day against about {expected:.1f} expected from the regular "
                                         f"session's density: the data is too thin to judge this session"}
                continue
        if s["total_return"] <= 0 or s["sharpe"] <= 0:
            hints[name] = {"verdict": "avoid", "size_multiplier": 0.0,
                           "reason": f"the strategy loses money in this session (return {s['total_return']:+.1%}, Sharpe {s['sharpe']:.2f})"}
            continue
        vol = s["volatility"]
        mult = 1.0 if name == REGULAR or not base_vol or vol <= base_vol or vol == 0 else max(MIN_MULTIPLIER, base_vol / vol)
        hints[name] = {"verdict": "trade" if mult >= 0.999 else "reduce", "size_multiplier": round(mult, 3),
                       "reason": f"return {s['total_return']:+.1%}, Sharpe {s['sharpe']:.2f}" + (
                           "" if mult >= 0.999 else f"; volatility {vol / base_vol:.1f}x the regular session's, so size x{mult:.2f}")}
    return hints


def approved_sessions(hints: dict[str, dict[str, Any]]) -> list[str]:
    """The sessions a strategy may trade: those whose verdict is trade or reduce."""
    return [n for n in TRADABLE_SESSIONS if (hints.get(n) or {}).get("verdict") in ("trade", "reduce")]
