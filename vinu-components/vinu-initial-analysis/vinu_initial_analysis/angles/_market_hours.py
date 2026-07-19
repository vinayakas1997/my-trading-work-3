"""Shared market-hours utilities — NYSE calendar, session classification, impact windows.

Provides:
  - NYSE calendar (holidays, DST transitions)
  - Session classification (pre-market, regular, after-hours, London, closed)
  - Impact window truncation at session boundaries
  - Pre-defined impact window sizes

Used by: news_price_causality, news_first_analysis, drawdown_deep_dive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

# ── NYSE Calendar ────────────────────────────────────────────────────────────

_NY = ZoneInfo("America/New_York")

_FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "New Year's Day",
    (7, 4): "Independence Day",
    (12, 25): "Christmas Day",
}

_NAMED_HOLIDAYS: dict[str, set[int]] = {
    "mlk_day": {2024, 2025, 2026, 2027, 2028},
    "presidents_day": {2024, 2025, 2026, 2027, 2028},
    "good_friday": {2024, 2025, 2026, 2027, 2028},
    "memorial_day": {2024, 2025, 2026, 2027, 2028},
    "juneteenth": {2024, 2025, 2026, 2027, 2028},
    "labor_day": {2024, 2025, 2026, 2027, 2028},
    "thanksgiving": {2024, 2025, 2026, 2027, 2028},
}


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> Date:
    first = Date(year, month, 1)
    first_dow = first.weekday()
    diff = (weekday - first_dow) % 7
    day = 1 + diff + 7 * (nth - 1)
    return Date(year, month, day)


def _last_weekday(year: int, month: int, weekday: int) -> Date:
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    last = Date(year, month, last_day)
    diff = (last.weekday() - weekday) % 7
    return last - timedelta(days=diff)


def _observed_date(d: Date) -> Date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _early_close_dates(year: int) -> set[Date]:
    results: set[Date] = set()
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    results.add(thanksgiving + timedelta(days=1))
    results.add(Date(year, 12, 24))
    return results


def is_nyse_holiday(d: Date) -> bool:
    if d.weekday() >= 5:
        return True
    month, day = d.month, d.day
    if (month, day) in _FIXED_HOLIDAYS:
        if _observed_date(d) == d:
            return True
    year = d.year
    if year in _NAMED_HOLIDAYS["mlk_day"] and d == _nth_weekday(year, 1, 0, 3):
        return True
    if year in _NAMED_HOLIDAYS["presidents_day"] and d == _nth_weekday(year, 2, 0, 3):
        return True
    if year in _NAMED_HOLIDAYS["memorial_day"] and d == _last_weekday(year, 5, 0):
        return True
    juneteenth = Date(year, 6, 19)
    if year in _NAMED_HOLIDAYS["juneteenth"] and d == _observed_date(juneteenth):
        return True
    if year in _NAMED_HOLIDAYS["labor_day"] and d == _nth_weekday(year, 9, 0, 1):
        return True
    tg = _nth_weekday(year, 11, 3, 4)
    if year in _NAMED_HOLIDAYS["thanksgiving"] and d == tg:
        return True
    return False


def is_dst(dt: datetime) -> bool:
    ny_dt = dt.astimezone(_NY)
    return bool(ny_dt.dst()) and ny_dt.dst().total_seconds() > 0


def get_market_sessions(dt: datetime) -> list[dict[str, Any]]:
    ny = dt.astimezone(_NY)
    d = ny.date()
    if is_nyse_holiday(d):
        return [{"name": "closed", "utc_start": 0, "utc_end": 24}]
    dst = is_dst(dt)
    ny_close = 20 if dst else 21
    ny_open = 13.5 if dst else 14.5
    return [
        {"name": "closed", "utc_start": 0, "utc_end": 7},
        {"name": "london", "utc_start": 7, "utc_end": 13},
        {"name": "ny_premarket", "utc_start": 13, "utc_end": ny_open},
        {"name": "ny_regular", "utc_start": ny_open, "utc_end": ny_close},
        {"name": "ny_afterhours", "utc_start": ny_close, "utc_end": 24},
    ]


# ── Session Classification ──────────────────────────────────────────────────

@dataclass
class SessionInfo:
    name: str
    utc_start_hour: int
    utc_end_hour: int


IMPACT_WINDOWS = {
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "1d": 86400,
}

_ALL_SESSION_NAMES = frozenset({
    "closed", "london", "ny_premarket", "ny_regular", "ny_afterhours",
})


def classify_session(ts: int) -> SessionInfo:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    hour = dt.hour + dt.minute / 60.0
    sessions = get_market_sessions(dt)
    for s in sessions:
        if s["utc_start"] <= hour < s["utc_end"]:
            return SessionInfo(s["name"], s["utc_start"], s["utc_end"])
    return SessionInfo("closed", 0, 24)


def iter_session_names() -> frozenset[str]:
    return _ALL_SESSION_NAMES


def impact_window_within_session(article_ts: int, window_sec: int) -> tuple[int, int]:
    session = classify_session(article_ts)
    if session.name == "closed":
        return (article_ts, article_ts)
    session_end = session.utc_end_hour * 3600
    article_day_start = (article_ts // 86400) * 86400
    max_ts = article_day_start + session_end
    return (article_ts, min(article_ts + window_sec, max_ts))


def get_session_boundaries(ts: int) -> list[SessionInfo]:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return [
        SessionInfo(s["name"], s["utc_start"], s["utc_end"])
        for s in get_market_sessions(dt)
    ]
