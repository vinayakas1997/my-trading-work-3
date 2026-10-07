"""US equity trading sessions: ONE definition for data, backtests, risk and orders.

The market is tradable around the clock on Alpaca (Sunday 20:00 ET to Friday 20:00 ET), in four sessions (New York time):

    premarket    04:00 - 09:30   limit orders only, thin liquidity
    regular      09:30 - 16:00   the only session market orders are accepted in
    afterhours   16:00 - 20:00   limit orders only
    overnight    20:00 - 04:00   limit orders only; symbols flagged `overnight_tradable` (Blue Ocean venue)

Outside Sunday 20:00 -> Friday 20:00 the market is `closed`. Holidays are not modelled: a holiday looks like a normal day here
(the broker clock is the authority for the regular session; bars simply do not exist on a holiday).

A session is decided from the bar's OPEN timestamp, in New York local time (daylight saving handled by zoneinfo).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

PREMARKET, REGULAR, AFTERHOURS, OVERNIGHT, CLOSED = "premarket", "regular", "afterhours", "overnight", "closed"
TRADABLE_SESSIONS = (PREMARKET, REGULAR, AFTERHOURS, OVERNIGHT)
EXTENDED_SESSIONS = (PREMARKET, AFTERHOURS, OVERNIGHT)

_OPEN_MIN = 9 * 60 + 30
_CLOSE_MIN = 16 * 60
_PRE_MIN = 4 * 60
_AFTER_END_MIN = 20 * 60


def session_of(ts: int | float) -> str:
    """The session a UTC epoch-seconds timestamp falls in."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(NY)
    minute = dt.hour * 60 + dt.minute
    weekday = dt.weekday()                      # Monday = 0 ... Sunday = 6
    if minute < _PRE_MIN:                       # 00:00-04:00: overnight, except the quiet weekend hours
        return OVERNIGHT if weekday in (0, 1, 2, 3, 4) else CLOSED
    if weekday >= 5 and not (weekday == 6 and minute >= _AFTER_END_MIN):
        return CLOSED
    if weekday == 6:                            # Sunday from 20:00 ET: the week's overnight session opens
        return OVERNIGHT
    if minute < _OPEN_MIN:
        return PREMARKET
    if minute < _CLOSE_MIN:
        return REGULAR
    if minute < _AFTER_END_MIN:
        return AFTERHOURS
    return OVERNIGHT if weekday <= 3 else CLOSED  # Friday after 20:00: closed until Sunday 20:00


def parse_sessions(spec: str | Iterable[str] | None) -> frozenset[str]:
    """`regular` (default) | `extended` (everything but regular) | `all` (every tradable session) | a comma list of names."""
    if spec is None:
        return frozenset({REGULAR})
    names = [p.strip().lower() for p in (spec.split(",") if isinstance(spec, str) else spec) if p and p.strip()]
    out: set[str] = set()
    for n in names:
        if n == "all":
            out.update(TRADABLE_SESSIONS)
        elif n == "extended":
            out.update(EXTENDED_SESSIONS)
        elif n in TRADABLE_SESSIONS:
            out.add(n)
        else:
            raise ValueError(f"unknown session {n!r}; use regular, extended, all or any of {', '.join(TRADABLE_SESSIONS)}")
    return frozenset(out or {REGULAR})


def spec_of(sessions: Iterable[str]) -> str:
    """Canonical text for a set of sessions (what a query string / config carries)."""
    s = frozenset(sessions)
    if s == frozenset(TRADABLE_SESSIONS):
        return "all"
    if s == frozenset(EXTENDED_SESSIONS):
        return "extended"
    return ",".join(x for x in TRADABLE_SESSIONS if x in s)


def keep_sessions(rows: list[dict], sessions: frozenset[str], *, ts_key: str = "bar_ts") -> list[dict]:
    """The rows whose bar falls in one of `sessions` (a no-op when every tradable session is wanted)."""
    if frozenset(TRADABLE_SESSIONS) <= sessions:
        return rows
    return [r for r in rows if session_of(int(r[ts_key])) in sessions]


def session_mask(bar_ts, sessions: frozenset[str]):
    """Boolean numpy array: which of the UTC epoch-second timestamps `bar_ts` (any array-like) fall in `sessions`.
    The vectorised twin of `session_of` (same rules, same answers; tested against it), fast enough for millions of bars."""
    import numpy as np
    import pandas as pd

    ts = np.asarray(bar_ts, dtype="int64")
    local = pd.to_datetime(ts, unit="s", utc=True).tz_convert(NY)
    minute = np.asarray(local.hour * 60 + local.minute)
    wd = np.asarray(local.weekday)
    weekday = wd <= 4
    out = np.full(ts.shape, CLOSED, dtype=object)
    out[weekday & (minute < _PRE_MIN)] = OVERNIGHT
    out[weekday & (minute >= _PRE_MIN) & (minute < _OPEN_MIN)] = PREMARKET
    out[weekday & (minute >= _OPEN_MIN) & (minute < _CLOSE_MIN)] = REGULAR
    out[weekday & (minute >= _CLOSE_MIN) & (minute < _AFTER_END_MIN)] = AFTERHOURS
    out[(wd <= 3) & (minute >= _AFTER_END_MIN)] = OVERNIGHT          # Mon-Thu evenings; Friday evening is closed
    out[(wd == 6) & (minute >= _AFTER_END_MIN)] = OVERNIGHT          # Sunday from 20:00
    return np.isin(out, list(sessions))
