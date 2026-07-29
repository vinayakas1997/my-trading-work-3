from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)


def risk_normalize(
    weights: dict[str, float],
    params: dict[str, Any] | None = None,
) -> dict[str, float]:
    max_w = (params or {}).get("max_weight", 0.25)
    max_short_w = (params or {}).get("max_short_weight", max_w)
    cash_floor = (params or {}).get("cash_floor", 0.10)
    allow_short = (params or {}).get("allow_short", True)

    if not weights:
        return {}

    if not allow_short:
        return _risk_normalize_long_only(weights, max_w, cash_floor)

    return _risk_normalize_with_shorts(weights, max_w, max_short_w, cash_floor)


def _risk_normalize_long_only(
    weights: dict[str, float],
    max_w: float,
    cash_floor: float,
) -> dict[str, float]:
    result = {}
    for sym, w in weights.items():
        if w > 0:
            result[sym] = min(w, max_w)

    total = sum(result.values())
    if not result or total <= 0:
        return result

    if total > (1.0 - cash_floor):
        scale = (1.0 - cash_floor) / total
        result = {sym: w * scale for sym, w in result.items()}

    return result


def _risk_normalize_with_shorts(
    weights: dict[str, float],
    max_w: float,
    max_short_w: float,
    cash_floor: float,
) -> dict[str, float]:
    longs: dict[str, float] = {}
    shorts: dict[str, float] = {}
    for sym, w in weights.items():
        if w >= 0:
            longs[sym] = min(w, max_w)
        else:
            shorts[sym] = max(w, -max_short_w)

    long_total = sum(longs.values())
    short_total = abs(sum(shorts.values())) if shorts else 0.0

    gross = long_total + short_total
    limit = 1.0 - cash_floor

    if gross > limit and gross > 0:
        scale = limit / gross
        if longs:
            longs = {sym: w * scale for sym, w in longs.items()}
        if shorts:
            shorts = {sym: w * scale for sym, w in shorts.items()}
        long_total *= scale
        short_total *= scale

    result = {}
    result.update(longs)
    result.update(shorts)
    return result


def risk_none(
    weights: dict[str, float],
    params: dict[str, Any] | None = None,
) -> dict[str, float]:
    return dict(weights)


def risk_shock_aware(
    weights: dict[str, float],
    params: dict[str, Any] | None = None,
) -> dict[str, float]:
    max_w = (params or {}).get("max_weight", 0.25)
    cash_floor = (params or {}).get("cash_floor", 0.10)
    allow_short = (params or {}).get("allow_short", True)
    max_short_w = (params or {}).get("max_short_weight", max_w)
    angle_signals = (params or {}).get("angle_signals", {})

    for sym in list(weights.keys()):
        shock = angle_signals.get(sym, {}).get("shock_personality", {})
        if not shock:
            continue
        vol_pers = shock.get("vol_persistence", {})
        if vol_pers and vol_pers.get("persistence", 0) > 0.95:
            weights[sym] *= 0.8
        gap_fill = shock.get("gap_fill_rate", {})
        if gap_fill and gap_fill.get("mean", 1.0) < 0.3:
            cash_floor = max(cash_floor, 0.20)

    if not allow_short:
        return _risk_normalize_long_only(weights, max_w, cash_floor)
    return _risk_normalize_with_shorts(weights, max_w, max_short_w, cash_floor)


RISK_METHODS = {
    "normalize": risk_normalize,
    "shock_aware": risk_shock_aware,
    "none": risk_none,
}


def run_risk(method: str, weights: dict[str, float], params: dict[str, Any] | None = None) -> dict[str, float]:
    func = RISK_METHODS.get(method)
    if func is None:
        LOG.warning("Unknown risk method '%s', using 'normalize'", method)
        return risk_normalize(weights, params)
    return func(weights, params)
