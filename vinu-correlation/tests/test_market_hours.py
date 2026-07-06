from datetime import datetime, timezone

from vinu_correlation.engine.market_hours import (
    IMPACT_WINDOWS,
    classify_session,
    impact_window_within_session,
)


def test_classify_session_regular():
    dt = datetime(2026, 7, 6, 15, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "regular"


def test_classify_session_pre_market():
    dt = datetime(2026, 7, 6, 10, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "pre_market"


def test_classify_session_after_hours():
    dt = datetime(2026, 7, 6, 21, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "after_hours"


def test_classify_session_closed():
    dt = datetime(2026, 7, 6, 3, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "closed"


def test_impact_window_truncated_at_session_boundary():
    dt = datetime(2026, 7, 6, 19, 30, 0, tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    frm, to = impact_window_within_session(ts, 3600)
    assert to - frm < 3600
    assert to == (ts // 86400) * 86400 + 20 * 3600


def test_impact_window_closed_session():
    dt = datetime(2026, 7, 6, 2, 0, 0, tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    frm, to = impact_window_within_session(ts, 3600)
    assert frm == to


def test_impact_windows_defined():
    assert IMPACT_WINDOWS["5m"] == 300
    assert IMPACT_WINDOWS["15m"] == 900
    assert IMPACT_WINDOWS["30m"] == 1800
    assert IMPACT_WINDOWS["1h"] == 3600
    assert IMPACT_WINDOWS["1d"] == 86400
