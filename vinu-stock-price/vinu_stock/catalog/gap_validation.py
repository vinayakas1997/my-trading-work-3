"""Bar gap detection for catalog health (TASK-S03)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SESSION_OPEN_MIN = 9 * 60 + 30
SESSION_CLOSE_MIN = 16 * 60
BAR_SEC = 60


def _is_weekday(dt_utc: datetime) -> bool:
    dt_ny = dt_utc.astimezone(NY)
    return dt_ny.weekday() < 5


def _in_regular_session(ts: int) -> bool:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if not _is_weekday(dt):
        return False
    dt_ny = dt.astimezone(NY)
    minute_of_day = dt_ny.hour * 60 + dt_ny.minute
    return SESSION_OPEN_MIN <= minute_of_day < SESSION_CLOSE_MIN


def count_session_gaps(bar_timestamps: list[int]) -> int:
    """Count missing 1m bars during regular NYSE session (simplified v1)."""
    if len(bar_timestamps) < 2:
        return 0
    ts_sorted = sorted(set(bar_timestamps))
    gaps = 0
    for prev, curr in zip(ts_sorted, ts_sorted[1:]):
        if not _in_regular_session(prev):
            continue
        expected = prev + BAR_SEC
        while expected < curr:
            if _in_regular_session(expected):
                gaps += 1
            expected += BAR_SEC
    return gaps
