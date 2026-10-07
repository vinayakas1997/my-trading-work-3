"""Metrics are annualised by the bars a year really holds: more sessions traded, more bars."""
from vinu_simulator.engine.metrics import periods_per_year_for_interval as ppy


def test_regular_hours_keep_the_existing_factors():
    assert ppy("15m") == 26 * 252 and ppy("1h", "regular") == 6.5 * 252 and ppy("4h") == 1.625 * 252 and ppy("1d") == 252


def test_all_sessions_are_twenty_four_hours_of_bars():
    assert ppy("15m", "all") == 96 * 252
    assert ppy("1h", "all") == 24 * 252
    assert ppy("1d", "all") == 252                      # a daily bar is one a day whatever the sessions


def test_extended_is_everything_but_regular_and_a_single_session_counts_its_hours():
    assert ppy("1h", "extended") == (5.5 + 4 + 8) * 252
    assert ppy("1h", "overnight") == 8 * 252
    assert ppy("15m", "regular,overnight") == (6.5 + 8) * 4 * 252
