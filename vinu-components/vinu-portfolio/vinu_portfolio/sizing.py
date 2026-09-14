from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)


def vol_targeting_position_size(
    risk_budget: float,
    realized_vol: float,
    target_vol: float = 0.15,
    max_leverage: float = 1.0,
) -> float:
    """Vol-targeting position sizing.

    Args:
        risk_budget: Capital allocated to this position (dollars).
        realized_vol: Annualized realized volatility (e.g. 0.20 for 20%).
        target_vol: Target annualized portfolio volatility.
        max_leverage: Maximum leverage multiplier.

    Returns:
        Target position size in dollars.

    Deliberately NOT delegated to vinu_infra.risk_math.vol_target_scale
    despite the similar intent -- that shared helper takes current_vol as
    *daily* and target_vol as *annual* (converting the latter internally),
    while this function's realized_vol/target_vol are both already
    annualized. Reusing it here without a unit conversion would silently
    change every existing caller's sizing math.
    """
    if realized_vol <= 0:
        return risk_budget
    raw_size = risk_budget * (target_vol / realized_vol)
    return min(raw_size, risk_budget * max_leverage)


def apply_position_sizing(
    weights: list[dict[str, Any]],
    total_capital: float,
    target_vol: float = 0.15,
    vol_estimates: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Apply vol-targeting position sizing to portfolio weights.

    Args:
        weights: List of {name, target_weight, ...} from the allocator.
        total_capital: Total portfolio capital in dollars.
        target_vol: Target annualized volatility.
        vol_estimates: Optional dict of strategy_name -> annualized vol.
                       When unavailable, uses the weight as-is (dollar
                       amount proportional to weight * capital) -- this is
                       intentional fail-open behavior, but it used to be
                       silent: passing `vol = target_vol` as the fallback
                       mathematically guarantees a 1.0 no-op ratio with no
                       trace of why. Now logged so a systematically missing
                       vol-estimation pipeline for a strategy is visible
                       instead of masquerading as "already at target vol".

    Returns:
        Same list with added 'position_size' key.
    """
    vol_estimates = vol_estimates or {}
    result = []
    missing = [w["name"] for w in weights if w["name"] not in vol_estimates]
    if missing:
        LOG.warning(
            "No vol_estimate for %d strategies (%s) -- sizing left unscaled (weight * capital) for them",
            len(missing), ", ".join(missing),
        )
    for w in weights:
        name = w["name"]
        weight = w["target_weight"]
        capital_alloc = weight * total_capital
        vol = vol_estimates.get(name, target_vol)
        position_size = vol_targeting_position_size(
            capital_alloc, vol, target_vol=target_vol,
        )
        result.append({**w, "position_size": round(position_size, 2)})
    return result
