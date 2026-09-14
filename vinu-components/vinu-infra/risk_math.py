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

import math
from typing import Any

_TRADING_DAYS_PER_YEAR = 252.0


def vol_target_scale(current_vol: Any, target_vol: float = 0.15) -> float:
    """target_vol (annual) / current_vol (daily), so size halves when
    realized daily vol doubles relative to the annualized target. target_vol
    is converted to a daily figure (/ sqrt(252)) before the ratio -- same
    units on both sides. Non-positive/non-finite/unparseable current_vol or
    target_vol = 1.0 (no scaling, fail-open). Never scales size *up* past
    1.0 -- a calm market does not license extra leverage here.

    The non-finite check is explicit rather than left to fall out of
    `min(1.0, ...)`'s argument order -- `min(1.0, nan)` happens to return
    1.0 in CPython, but `min(nan, 1.0)` would silently return `nan` instead,
    so this must not depend on which argument comes first."""
    try:
        cur = float(current_vol)
        tgt = float(target_vol)
    except (TypeError, ValueError):
        return 1.0
    if not (math.isfinite(cur) and math.isfinite(tgt)) or cur <= 0.0 or tgt <= 0.0:
        return 1.0
    target_daily = tgt / (_TRADING_DAYS_PER_YEAR ** 0.5)
    return min(1.0, target_daily / cur)


def forecast_confidence_scale(confidence: Any, floor: float = 0.5) -> float:
    """confidence as a direct fraction of the caller's requested size,
    floored so a real forecast is dampened, never zeroed, by conviction
    alone. None/non-positive/non-finite confidence = 1.0 (no scaling,
    fail-open -- the caller didn't supply a usable forecast, not evidence
    the forecast is bad). Explicit finite check for the same reason as
    `vol_target_scale` -- not left to fall out of `min()`/`max()` argument
    order."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(c) or c <= 0.0:
        return 1.0
    return max(float(floor), min(1.0, c))


def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction_of_kelly: float = 1.0,
) -> float:
    """Kelly criterion for a binary win/loss bet: f* = p - (1-p)/b, where p
    is win probability and b = avg_win/avg_loss is the payoff ratio.

    This exact formula used to be reimplemented independently in
    vinu-tools (`compute/risk/position_sizing.py`'s `kelly_optimal_fraction`)
    and vinu-simulator (`engine/sizing.py`'s `FractionalKellySizer`) -- both
    services already install vinu-infra (confirmed via each Dockerfile), so
    this is the single source of truth both now delegate to, matching the
    `vol_target_scale` unification above.

    avg_loss<=0, avg_win<=0, or win_rate outside (0,1) = 0.0 (no edge
    estimate possible from a degenerate sample -- same fail-safe as the
    original implementations). avg_win<=0 is checked explicitly rather than
    left to fall out of the division below -- b = avg_win/avg_loss = 0.0
    would otherwise raise ZeroDivisionError computing f_star, discovered
    when vinu-agent's full_kelly_fraction (a 3rd caller, unified here after
    vinu-tools and vinu-simulator) was found to pass avg_win=payoff_ratio
    directly, a value degenerate inputs upstream can legitimately drive to
    0."""
    if avg_loss <= 0 or avg_win <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    f_star = (p * b - q) / b
    return max(0.0, f_star * fraction_of_kelly)


def cvar_exceeds(cvar_95: Any, threshold: float = 0.03) -> bool:
    """True if tail risk blocks sizing. cvar_95 as positive loss fraction
    (0.04 = 4% daily). Non-finite/unparseable cvar_95 or threshold = False
    (fail-open) -- same convention as `vol_target_scale` and
    `forecast_confidence_scale` above: garbage/missing input here means "we
    have no usable signal", not "block the trade". The caller
    (vinu-agent's position_sizing.py) already only invokes this when a
    real, non-None cvar_95 was computed; this is a second, explicit line of
    defense against a NaN/inf value slipping through as if it exceeded the
    threshold (float('nan') > x is always False in Python, so this needs to
    be explicit rather than left to fall out of the raw comparison)."""
    try:
        cur = float(cvar_95)
        thr = float(threshold)
    except (TypeError, ValueError):
        return False
    if not (math.isfinite(cur) and math.isfinite(thr)):
        return False
    return cur > thr
