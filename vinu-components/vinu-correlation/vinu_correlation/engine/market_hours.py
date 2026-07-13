from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


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


def classify_session(ts: int) -> SessionInfo:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    hour = dt.hour
    if 8 <= hour < 13:
        return SessionInfo("pre_market", 8, 13)
    elif 13 <= hour < 20:
        return SessionInfo("regular", 13, 20)
    elif 20 <= hour < 24:
        return SessionInfo("after_hours", 20, 24)
    else:
        return SessionInfo("closed", 0, 8)


def impact_window_within_session(article_ts: int, window_sec: int) -> tuple[int, int]:
    session = classify_session(article_ts)
    if session.name == "closed":
        return (article_ts, article_ts)
    session_end = session.utc_end_hour * 3600
    article_day_start = (article_ts // 86400) * 86400
    max_ts = article_day_start + session_end
    return (article_ts, min(article_ts + window_sec, max_ts))
