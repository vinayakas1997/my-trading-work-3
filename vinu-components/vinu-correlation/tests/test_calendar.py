from datetime import datetime, timezone

from vinu_correlation.engine.calendar import (
    get_market_sessions,
    is_dst,
    is_nyse_holiday,
)


def test_is_dst_july():
    dt = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert is_dst(dt) is True


def test_is_dst_january():
    dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert is_dst(dt) is False


def test_is_nyse_holiday_new_years():
    assert is_nyse_holiday(datetime(2026, 1, 1).date()) is True
    assert is_nyse_holiday(datetime(2026, 1, 2).date()) is False


def test_is_nyse_holiday_weekend():
    sat = datetime(2026, 7, 11).date()
    assert sat.weekday() == 5
    assert is_nyse_holiday(sat) is True


def test_is_nyse_holiday_thanksgiving():
    assert is_nyse_holiday(datetime(2026, 11, 26).date()) is True  # 4th Thu


def test_is_nyse_holiday_juneteenth():
    juneteenth = datetime(2026, 6, 19).date()
    assert juneteenth.weekday() == 4  # Friday
    assert is_nyse_holiday(juneteenth) is True


def test_get_market_sessions_july_dst():
    dt = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    sessions = get_market_sessions(dt)
    names = [s["name"] for s in sessions]
    assert names == ["closed", "london", "ny_premarket", "ny_regular", "ny_afterhours"]
    ny_reg = sessions[3]
    assert ny_reg["utc_start"] == 14
    assert ny_reg["utc_end"] == 20
    ny_after = sessions[4]
    assert ny_after["utc_start"] == 20
    assert ny_after["utc_end"] == 24


def test_get_market_sessions_january_standard():
    dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)
    sessions = get_market_sessions(dt)
    ny_reg = sessions[3]
    assert ny_reg["name"] == "ny_regular"
    assert ny_reg["utc_start"] == 14
    assert ny_reg["utc_end"] == 21
    ny_after = sessions[4]
    assert ny_after["utc_start"] == 21
    assert ny_after["utc_end"] == 24


def test_get_market_sessions_holiday():
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    sessions = get_market_sessions(dt)
    assert len(sessions) == 1
    assert sessions[0]["name"] == "closed"
