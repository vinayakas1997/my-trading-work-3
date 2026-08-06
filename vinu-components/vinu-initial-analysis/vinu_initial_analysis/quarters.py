"""Calendar-period boundary helper for the tier2 [start, period-end) window.

tier2 is documented (see ../New-talk-/Final-implementation/limitations_and_other_info.md
and 03-actual-plan-findings/03-storage-design.md) as scheduled quarterly and
immutable — every ticker's tier2 run must share the same window end so runs
stay comparable to each other, to their own prior-period run, and *across
tickers* (a ticker added mid-period still gets the same shared window as
every other ticker, since the window never depends on when a given ticker
joined the watchlist — only on VINU_STAGE1_START_DATE and the calendar).

Using wall-clock "now" as that end defeats has_existing_run()'s exact-match
dedup (it would never match twice, since "now" always differs) and reduces
"scheduled quarterly" to "recompute on every poll cycle." This module makes
the end genuinely period-stable: it only changes when a period actually
closes, and the period length itself is configurable (VINU_TIER2_PERIOD_MONTHS,
default 3 for calendar quarters) rather than hardcoded, in case the cadence
ever needs to change.

The boundary is the **exclusive** start of the current (in-progress) period
— equivalently, "everything up through the last fully completed period" —
not the last completed period's own last day. This matches how `to_ts` is
already treated elsewhere in this codebase (price_client.py's pagination
loop is `while cursor < to_ts`, i.e. an exclusive upper bound) and avoids
needing to compute month-end days (28/29/30/31) at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

DEFAULT_PERIOD_MONTHS = 3


def last_completed_period_end(
    now: datetime | None = None, period_months: int = DEFAULT_PERIOD_MONTHS
) -> datetime:
    """UTC start of the current calendar period (exclusive upper bound).

    Periods are calendar-aligned, starting from January (e.g. with the
    default period_months=3: Q1 Jan-Mar, Q2 Apr-Jun, Q3 Jul-Sep, Q4 Oct-Dec).
    `period_months` must evenly divide 12 (1, 2, 3, 4, 6, or 12) for the
    periods to land on clean calendar-year boundaries.

    Stays constant for the entire duration of the current period (e.g. all
    of Q3 returns the same July 1 00:00:00 boundary), so scheduled runs
    within the same period share the same window and correctly dedup via
    has_existing_run() — only advancing once the next period starts.
    """
    if 12 % period_months != 0:
        raise ValueError(f"period_months must evenly divide 12, got {period_months}")
    now = now or datetime.now(tz=timezone.utc)
    current_period_idx = (now.month - 1) // period_months  # 0-indexed
    start_month = current_period_idx * period_months + 1
    return datetime(now.year, start_month, 1, tzinfo=timezone.utc)
