"""Shared calendar/session tagging for angle backtest rows.

Wraps the real, already-used session classifier in `_market_hours.py`
instead of inventing a second, competing session scheme. See
New-talk-/05-storage-enhancement-levels/plan.md for why this mapping was
chosen over the aspirational Tokyo/London/NY/Sydney scheme.

Every angle's walk-forward backtest code must tag its rows through
`tag_row` — never hand-roll session/day/week/quarter logic per angle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_initial_analysis.angles._market_hours import classify_session

# classify_session() names -> (session, subsession), per the mapping
# decided in 05-storage-enhancement-levels/plan.md.
_SESSION_MAP: dict[str, tuple[str, str | None]] = {
    "closed": ("closed", None),
    "london": ("london", None),
    "ny_premarket": ("ny", "premarket"),
    "ny_regular": ("ny", "markethours"),
    "ny_afterhours": ("ny", "afterhours"),
}


def tag_row(bar_ts: int) -> dict[str, Any]:
    """Calendar/session tags for a single bar timestamp (UTC unix seconds).

    Returns session, subsession, day_of_week, week_of_month, month, quarter.
    """
    dt = datetime.fromtimestamp(bar_ts, tz=timezone.utc)
    info = classify_session(bar_ts)
    session, subsession = _SESSION_MAP.get(info.name, (info.name, None))
    return {
        "session": session,
        "subsession": subsession,
        "day_of_week": dt.strftime("%A").lower(),
        "week_of_month": (dt.day - 1) // 7 + 1,
        "month": dt.month,
        "quarter": (dt.month - 1) // 3 + 1,
    }
