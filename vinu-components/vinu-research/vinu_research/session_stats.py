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
    out: dict[str, dict[str, Any]] = {}
    for name in TRADABLE_SESSIONS:
        m = session_mask(stamps.to_numpy(), frozenset({name}))
        r = values[m]
        bars = int(m.sum())
        vol = float(r.std(ddof=1)) if bars > 1 else 0.0
        mean = float(r.mean()) if bars else 0.0
        out[name] = {
            "bars": bars,
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
    hints: dict[str, dict[str, Any]] = {}
    for name in TRADABLE_SESSIONS:
        s = breakdown.get(name) or {}
        bars, traded = int(s.get("bars", 0)), int(s.get("traded_bars", 0))
        if bars < min_bars or traded < min_bars // 4:
            hints[name] = {"verdict": "insufficient_data", "size_multiplier": 0.0,
                           "reason": f"{bars} bars ({traded} with a position); at least {min_bars} bars are needed to judge a session"}
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
