from datetime import datetime, timezone

from vinu_correlation.engine.market_hours import (
    IMPACT_WINDOWS,
    classify_session,
    impact_window_within_session,
    iter_session_names,
)


def test_classify_session_ny_regular():
    dt = datetime(2026, 7, 6, 15, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_regular"


def test_classify_session_london():
    dt = datetime(2026, 7, 6, 10, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "london"


def test_classify_session_ny_premarket():
    dt = datetime(2026, 7, 6, 13, 30, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_premarket"


def test_classify_session_ny_afterhours():
    dt = datetime(2026, 7, 6, 22, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_afterhours"


def test_classify_session_closed():
    dt = datetime(2026, 7, 6, 3, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "closed"


def test_classify_session_boundary_exact():
    dt = datetime(2026, 7, 6, 7, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "london"

    dt = datetime(2026, 7, 6, 13, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_premarket"

    dt = datetime(2026, 7, 6, 14, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_regular"

    dt = datetime(2026, 7, 6, 21, 0, 0, tzinfo=timezone.utc)
    session = classify_session(int(dt.timestamp()))
    assert session.name == "ny_afterhours"


def test_impact_window_truncated_at_session_boundary():
    # Use a timestamp 10 min before ny_regular ends during DST
    dt = datetime(2026, 7, 6, 19, 50, 0, tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    frm, to = impact_window_within_session(ts, 3600)
    assert to - frm < 3600
    # session is ny_regular (14-20 DST), truncate at 20:00 UTC
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


def test_iter_session_names():
    names = iter_session_names()
    assert "closed" in names
    assert "london" in names
    assert "ny_premarket" in names
    assert "ny_regular" in names
    assert "ny_afterhours" in names
    assert len(names) == 5
