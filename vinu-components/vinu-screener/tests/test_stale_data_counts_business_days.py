"""Found in the first full-chain run: on a Monday morning every ticker was flagged stale (Friday's daily bar, stamped
00:00 UTC, is more than 3 calendar days old) and lost 10 points, which buried the real ranking."""

from datetime import datetime, timezone

import pandas as pd

from vinu_screener.rankers.runner import _is_stale


def _df(last: str) -> pd.DataFrame:
    return pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex([last], tz="UTC"))


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_fridays_bar_is_fresh_on_monday_morning_and_all_monday():
    assert not _is_stale(_df("2026-10-02"), now=_at("2026-10-05T00:36:00"))
    assert not _is_stale(_df("2026-10-02"), now=_at("2026-10-05T20:00:00"))


def test_a_bar_missing_more_than_three_trading_days_is_stale():
    assert _is_stale(_df("2026-09-28"), now=_at("2026-10-05T10:00:00"))     # Monday bar, a week later
    assert not _is_stale(_df("2026-10-01"), now=_at("2026-10-05T10:00:00"))
