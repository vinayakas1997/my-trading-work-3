"""Rule-based protection for a live-decision position (plan item 2.3,
logic-audit-2026-10-02 A3, the-inconsistencies-v2).

A trade-plan position gets a broker-side backstop stop plus invalidation and
time-stop rules evaluated every cycle. A position opened by a live-decision
EXECUTE had none of that -- only the LLM review every N bars and portfolio
halts. These two optional, per-strategy rules close that gap without needing
an LLM call:

* stop_pct       -- exit when price has moved this fraction AGAINST the entry
                    (0.05 = 5%). Needs the entry reference price.
* max_hold_bars  -- exit once this many bars have elapsed since the position
                    opened. Needs no price.

Both are 0 (off) by default, like `live_decision_position_size`: there is no
safe invented number, so the strategy author opts in. Pure functions only --
no I/O -- so every edge case is testable without a database.

Known approximations, stated rather than hidden:
* `entry_price` is the price the first priced scheduler cycle after the
  position opened sized the order on (the last daily close), not the broker
  fill price.
* Bars elapsed is `(bar_ts - opened_bar_ts) // timeframe_seconds`, i.e. calendar
  time in bar units -- the same convention the state tracker's grace window
  already uses -- so it counts overnight and weekend gaps as bars on intraday
  timeframes.
"""

from __future__ import annotations

import math


def _finite_positive(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def evaluate_position_rules(
    *,
    position_size: float,
    entry_price: float | None,
    last_close: float,
    opened_bar_ts: int,
    bar_ts: int,
    timeframe_seconds: int,
    stop_pct: float = 0.0,
    max_hold_bars: int = 0,
) -> tuple[str, str] | None:
    """(rule_name, human detail) when a rule says EXIT, else None.

    A negative `position_size` is a short: its stop triggers on a price RISE.
    Stop is checked before max-hold (a stop is the more urgent reason).
    Any unusable input disables that rule rather than guessing -- a rule can
    only ever cause an exit it can fully justify."""
    if stop_pct and stop_pct > 0 and _finite_positive(entry_price) and _finite_positive(last_close):
        is_short = position_size < 0
        if is_short:
            level = entry_price * (1.0 + stop_pct)
            if last_close >= level:
                return (
                    "stop_loss",
                    f"short stop: close {last_close:.4f} >= {level:.4f} "
                    f"(entry {entry_price:.4f} + {stop_pct:.1%})",
                )
        else:
            level = entry_price * (1.0 - stop_pct)
            if last_close <= level:
                return (
                    "stop_loss",
                    f"long stop: close {last_close:.4f} <= {level:.4f} "
                    f"(entry {entry_price:.4f} - {stop_pct:.1%})",
                )

    if max_hold_bars and max_hold_bars > 0 and timeframe_seconds > 0:
        bars_held = (bar_ts - opened_bar_ts) // timeframe_seconds
        if bars_held >= max_hold_bars:
            return ("max_hold", f"held {bars_held} bars >= max_hold_bars {max_hold_bars}")

    return None
