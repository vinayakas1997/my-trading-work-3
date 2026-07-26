from __future__ import annotations

import numpy as np
from scipy import stats as _stats

from vinu_tools.compute.risk.volatility import realized_volatility


def expected_move_from_vol(
    volatility: float,
    confidence: float = 0.68,
) -> float:
    z = _stats.norm.ppf((1 + confidence) / 2)
    return volatility * z


def expected_range(
    volatility: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    z = _stats.norm.ppf((1 + confidence) / 2)
    half_range = volatility * z
    return -half_range, half_range


def straddle_approximation(
    volatility: float,
    spot: float,
    time_to_expiry: float,
) -> float:
    return spot * volatility * np.sqrt(time_to_expiry) * 0.8


def expected_move_over_period(
    daily_volatility: float,
    days: int,
    confidence: float = 0.68,
) -> float:
    period_vol = daily_volatility * np.sqrt(days)
    return expected_move_from_vol(period_vol, confidence)
