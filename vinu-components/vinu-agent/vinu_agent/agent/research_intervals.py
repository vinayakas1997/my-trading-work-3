"""Which bar sizes every strategy idea is researched on, and over how long a window.

A strategy that has an edge on daily bars may have none on 15-minute bars and the reverse, and a daily-only test hides
nearly every trade an intraday system would make (15 minutes gives ~26 bars a day to a daily bar's 1). So the planner
hands the research team the same ticker once per bar size, each judged by the SAME unchanged promotion bar on its own
bars; the promotion bar is not touched here.

`VINU_SWEEP_INTERVALS` (default "1d,4h,1h,15m") is the existing research knob, with its spellings normalised: the price
service and simulator accept only lowercase `1m 5m 15m 30m 1h 4h 1d`, and `15min`/`1H`/`1D` were rejected with a 422.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

SUPPORTED = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
DEFAULT_INTERVALS = "1d,4h,1h,15m"

_ALIASES = {"15min": "15m", "30min": "30m", "5min": "5m", "1min": "1m", "60m": "1h", "1hour": "1h", "1day": "1d", "daily": "1d"}

# History per bar size: enough bars for a stable result without fetching a decade of 15-minute data. 15m is ~26 bars a
# day, so a year is ~6,500 bars; daily needs years to see enough trades.
WINDOW_DAYS = {"1d": 4 * 365, "4h": 3 * 365, "1h": 2 * 365, "30m": 365, "15m": 365, "5m": 180, "1m": 60}


def normalise_interval(raw: str) -> str:
    key = raw.strip().lower()
    key = _ALIASES.get(key, key)
    if key not in SUPPORTED:
        raise ValueError(f"unsupported interval {raw!r}; use one of {', '.join(SUPPORTED)}")
    return key


def research_intervals(env: str | None = None) -> list[str]:
    """Bar sizes to research each idea on, normalised, de-duplicated, in the configured order."""
    raw = os.environ.get("VINU_SWEEP_INTERVALS", DEFAULT_INTERVALS) if env is None else env
    out: list[str] = []
    for part in raw.split(","):
        if part.strip():
            iv = normalise_interval(part)
            if iv not in out:
                out.append(iv)
    return out or [normalise_interval(p) for p in DEFAULT_INTERVALS.split(",")]


def window_for(interval: str, *, today: date | None = None) -> tuple[str, str]:
    """(from_date, to_date) ISO dates ending at the last completed day."""
    end = (today or date.today()) - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS[normalise_interval(interval)])
    return start.isoformat(), end.isoformat()
