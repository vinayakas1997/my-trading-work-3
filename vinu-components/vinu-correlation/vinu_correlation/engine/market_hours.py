from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from vinu_correlation.engine.calendar import get_market_sessions, is_nyse_holiday


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
    hour = dt.hour
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
