"""Shared position-sizing risk math used by both vinu-agent and vinu-live.

These two are separate deployable services with no other shared package for
this kind of logic, so each used to carry its own copy. `vol_target_scale`
had already drifted: vinu-agent's copy compared current_vol and target_vol
directly with no unit conversion and floored the result at 0.25x; vinu-live's
copy (the one actually exercised by a live caller -- see
vinu_live/trade_plan/orchestrator.py's `_maybe_enter`) correctly treats
current_vol as a *daily* vol and target_vol as *annual*, converting the
target to daily (/ sqrt(252)) before comparing, with no floor. This module
keeps vinu-live's formula as the one source of truth for both.
"""

from __future__ import annotations

from typing import Any

_TRADING_DAYS_PER_YEAR = 252.0


def vol_target_scale(current_vol: Any, target_vol: float = 0.15) -> float:
    """target_vol (annual) / current_vol (daily), so size halves when
    realized daily vol doubles relative to the annualized target. target_vol
    is converted to a daily figure (/ sqrt(252)) before the ratio -- same
    units on both sides. Non-positive/unparseable current_vol or target_vol
    = 1.0 (no scaling, fail-open). Never scales size *up* past 1.0 -- a calm
    market does not license extra leverage here."""
    try:
        cur = float(current_vol)
        tgt = float(target_vol)
    except (TypeError, ValueError):
        return 1.0
    if cur <= 0.0 or tgt <= 0.0:
        return 1.0
    target_daily = tgt / (_TRADING_DAYS_PER_YEAR ** 0.5)
    return min(1.0, target_daily / cur)


def forecast_confidence_scale(confidence: Any, floor: float = 0.5) -> float:
    """confidence as a direct fraction of the caller's requested size,
    floored so a real forecast is dampened, never zeroed, by conviction
    alone. None/non-positive confidence = 1.0 (no scaling, fail-open --
    the caller didn't supply a forecast, not evidence the forecast is bad)."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 1.0
    if c <= 0.0:
        return 1.0
    return max(float(floor), min(1.0, c))


def cvar_exceeds(cvar_95: Any, threshold: float = 0.03) -> bool:
    """True if tail risk blocks sizing. cvar_95 as positive loss fraction
    (0.04 = 4% daily)."""
    try:
        return float(cvar_95) > float(threshold)
    except (TypeError, ValueError):
        return False
