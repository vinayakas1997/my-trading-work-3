"""One definition of the trading sessions, in New York time, daylight saving included."""
from __future__ import annotations

from datetime import datetime

import pytest

from vinu_infra.sessions import (
    AFTERHOURS, CLOSED, NY, OVERNIGHT, PREMARKET, REGULAR, TRADABLE_SESSIONS, keep_sessions, parse_sessions, session_of, spec_of,
)


def ts(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=NY).timestamp()


# 2026-10-05 is a Monday (EDT, UTC-4); 2026-01-12 is a Monday (EST, UTC-5)
@pytest.mark.parametrize("when, expected", [
    ((2026, 10, 5, 3, 59), OVERNIGHT),       # Monday early morning: the overnight session that opened Sunday 20:00
    ((2026, 10, 5, 4, 0), PREMARKET),
    ((2026, 10, 5, 9, 29), PREMARKET),
    ((2026, 10, 5, 9, 30), REGULAR),
    ((2026, 10, 5, 15, 59), REGULAR),
    ((2026, 10, 5, 16, 0), AFTERHOURS),
    ((2026, 10, 5, 19, 59), AFTERHOURS),
    ((2026, 10, 5, 20, 0), OVERNIGHT),
    ((2026, 10, 5, 23, 59), OVERNIGHT),
    ((2026, 10, 6, 0, 0), OVERNIGHT),         # Tuesday 00:00
    ((2026, 10, 9, 15, 59), REGULAR),         # Friday
    ((2026, 10, 9, 20, 0), CLOSED),           # Friday 20:00: closed for the weekend
    ((2026, 10, 10, 12, 0), CLOSED),          # Saturday
    ((2026, 10, 11, 12, 0), CLOSED),          # Sunday before 20:00
    ((2026, 10, 11, 20, 0), OVERNIGHT),       # Sunday 20:00: the week's overnight session opens
    ((2026, 10, 10, 2, 0), CLOSED),           # Saturday 02:00 (Friday night is not tradable)
])
def test_sessions_in_new_york_time(when, expected):
    assert session_of(ts(*when)) == expected


def test_daylight_saving_moves_the_utc_hours_but_not_the_sessions():
    assert session_of(ts(2026, 1, 12, 9, 30)) == REGULAR          # EST: 14:30 UTC
    assert session_of(ts(2026, 10, 5, 9, 30)) == REGULAR          # EDT: 13:30 UTC
    assert ts(2026, 1, 12, 9, 30) % 86400 != ts(2026, 10, 5, 9, 30) % 86400


def test_parse_and_spec_round_trip():
    assert parse_sessions(None) == frozenset({REGULAR})
    assert parse_sessions("all") == frozenset(TRADABLE_SESSIONS)
    assert parse_sessions("extended") == frozenset({PREMARKET, AFTERHOURS, OVERNIGHT})
    assert parse_sessions("regular, overnight") == frozenset({REGULAR, OVERNIGHT})
    assert spec_of(parse_sessions("all")) == "all" and spec_of({REGULAR, OVERNIGHT}) == "regular,overnight"
    with pytest.raises(ValueError, match="unknown session"):
        parse_sessions("lunch")


def test_keep_sessions_filters_rows_by_bar_open_time():
    rows = [{"bar_ts": int(ts(2026, 10, 5, h))} for h in (3, 5, 10, 17, 21)]
    kept = lambda spec: [session_of(r["bar_ts"]) for r in keep_sessions(rows, parse_sessions(spec))]
    assert kept("regular") == [REGULAR]
    assert kept("extended") == [OVERNIGHT, PREMARKET, AFTERHOURS, OVERNIGHT]
    assert len(keep_sessions(rows, parse_sessions("all"))) == 5


def test_the_vectorised_mask_agrees_with_the_scalar_rule_on_a_year_of_random_minutes():
    import numpy as np

    from vinu_infra.sessions import session_mask

    rng = np.random.default_rng(3)
    stamps = rng.integers(int(ts(2025, 11, 1, 0)), int(ts(2026, 11, 30, 0)), 4000)
    for spec in ("regular", "extended", "premarket,overnight", "afterhours"):
        wanted = parse_sessions(spec)
        assert session_mask(stamps, wanted).tolist() == [session_of(int(t)) in wanted for t in stamps], spec
