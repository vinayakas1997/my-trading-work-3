from datetime import date

import pytest

from vinu_agent.agent.research_intervals import normalise_interval, research_intervals, window_for


def test_default_is_the_four_bar_sizes_in_order():
    assert research_intervals("") == ["1d", "4h", "1h", "15m"]
    assert research_intervals("1d,4h,1h,15m") == ["1d", "4h", "1h", "15m"]


def test_spellings_the_services_reject_are_normalised():
    assert research_intervals("1D, 4H, 1H, 15min") == ["1d", "4h", "1h", "15m"]
    assert research_intervals("15min,15m,15M") == ["15m"]            # de-duplicated


def test_an_unknown_interval_fails_loudly_instead_of_422_later():
    with pytest.raises(ValueError, match="unsupported interval"):
        normalise_interval("3h")


def test_windows_end_at_the_last_completed_day_and_shrink_with_bar_size():
    today = date(2026, 10, 7)
    assert window_for("15m", today=today)[1] == "2026-10-06"
    d1 = date.fromisoformat(window_for("1d", today=today)[0])
    m15 = date.fromisoformat(window_for("15m", today=today)[0])
    assert d1 < m15 < date(2026, 10, 6)
