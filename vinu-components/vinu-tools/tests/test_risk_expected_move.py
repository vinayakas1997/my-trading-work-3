import numpy as np
from vinu_tools.compute.risk.expected_move import (
    expected_move_from_vol,
    expected_range,
    straddle_approximation,
    expected_move_over_period,
)


def test_expected_move_from_vol():
    vol = 0.20  # 20% annualized
    move = expected_move_from_vol(vol, confidence=0.68)
    assert abs(move / vol - 1.0) < 0.02  # ~1 sigma (z~0.994)


def test_expected_move_95pct():
    vol = 0.20
    move = expected_move_from_vol(vol, confidence=0.95)
    assert move > vol  # wider for higher confidence


def test_expected_range():
    vol = 0.20
    lo, hi = expected_range(vol, confidence=0.95)
    assert lo < 0
    assert hi > 0
    assert abs(lo) == hi


def test_straddle_approximation():
    result = straddle_approximation(volatility=0.20, spot=100, time_to_expiry=30/365)
    assert result > 0
    assert result < 100


def test_straddle_approximation_zero_vol():
    result = straddle_approximation(volatility=0.0, spot=100, time_to_expiry=30/365)
    assert result == 0


def test_expected_move_over_period():
    daily_vol = 0.01
    move_1d = expected_move_over_period(daily_vol, days=1, confidence=0.68)
    assert abs(move_1d - 0.01) < 0.0005  # ~0.01 (z~0.994)
    move_5d = expected_move_over_period(daily_vol, days=5, confidence=0.68)
    expected = 0.01 * np.sqrt(5)
    assert abs(move_5d / expected - 1.0) < 0.02
