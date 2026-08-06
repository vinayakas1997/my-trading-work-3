from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vinu_initial_analysis.quarters import last_completed_period_end


def test_mid_quarter_floors_to_quarter_start():
    now = datetime(2026, 8, 6, tzinfo=timezone.utc)
    assert last_completed_period_end(now) == datetime(2026, 7, 1, tzinfo=timezone.utc)


def test_first_quarter_of_year():
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert last_completed_period_end(now) == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_exact_period_boundary_is_stable():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    assert last_completed_period_end(now) == datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_stable_across_entire_quarter():
    early = last_completed_period_end(datetime(2026, 7, 1, tzinfo=timezone.utc))
    late = last_completed_period_end(datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc))
    assert early == late == datetime(2026, 7, 1, tzinfo=timezone.utc)


def test_advances_once_next_quarter_starts():
    q3 = last_completed_period_end(datetime(2026, 9, 30, tzinfo=timezone.utc))
    q4 = last_completed_period_end(datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert q3 != q4
    assert q4 == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_configurable_period_months():
    now = datetime(2026, 8, 6, tzinfo=timezone.utc)
    assert last_completed_period_end(now, period_months=6) == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert last_completed_period_end(now, period_months=1) == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert last_completed_period_end(now, period_months=12) == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_invalid_period_months_rejected():
    with pytest.raises(ValueError):
        last_completed_period_end(period_months=5)
