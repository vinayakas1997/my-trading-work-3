from __future__ import annotations

from vinu_initial_analysis.angles._market_hours import classify_session
from vinu_initial_analysis.angles._tagging import tag_row


def test_ny_regular_session_maps_to_ny_markethours():
    # 2024-05-15 14:30 UTC, DST in effect -> ny_regular per _market_hours.
    ts = 1715782200
    assert classify_session(ts).name == "ny_regular"
    tags = tag_row(ts)
    assert tags["session"] == "ny"
    assert tags["subsession"] == "markethours"


def test_overnight_is_closed_with_no_subsession():
    # 2024-05-15 03:00 UTC -> closed.
    ts = 1715742000
    tags = tag_row(ts)
    assert tags["session"] == "closed"
    assert tags["subsession"] is None


def test_london_session_has_no_subsession():
    # 2024-05-15 08:00 UTC -> london.
    ts = 1715760000
    assert classify_session(ts).name == "london"
    tags = tag_row(ts)
    assert tags["session"] == "london"
    assert tags["subsession"] is None


def test_calendar_fields_are_correct():
    # 2024-05-15 is a Wednesday, 3rd week of May, Q2.
    ts = 1715782200
    tags = tag_row(ts)
    assert tags["day_of_week"] == "wednesday"
    assert tags["week_of_month"] == 3
    assert tags["month"] == 5
    assert tags["quarter"] == 2


def test_all_five_classify_session_names_are_mapped():
    from vinu_initial_analysis.angles._tagging import _SESSION_MAP
    from vinu_initial_analysis.angles._market_hours import iter_session_names

    assert set(_SESSION_MAP.keys()) == set(iter_session_names())
