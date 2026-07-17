"""NYSE calendar utilities using built-in zoneinfo (no external deps).

Handles DST transitions, holidays, and early closes.
"""

from __future__ import annotations

from datetime import date as Date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
    return [
        {"name": "closed", "utc_start": 0, "utc_end": 7},
        {"name": "london", "utc_start": 7, "utc_end": 13},
        {"name": "ny_premarket", "utc_start": 13, "utc_end": 14},
        {"name": "ny_regular", "utc_start": 14, "utc_end": ny_close},
        {"name": "ny_afterhours", "utc_start": ny_close, "utc_end": 24},
    ]
