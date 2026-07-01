"""Tests for gap validation (TASK-S03)."""

from vinu_stock.catalog.gap_validation import count_session_gaps


def test_count_session_gaps_zero_for_consecutive():
    # 2024-06-03 13:30 UTC = 9:30 ET (session open)
    base = 1_717_421_400
    ts = [base, base + 60]
    assert count_session_gaps(ts) == 0


def test_count_session_gaps_detects_missing():
    base = 1_717_421_400
    ts = [base, base + 120]  # skip one minute
    assert count_session_gaps(ts) >= 1
