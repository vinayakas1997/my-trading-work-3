from __future__ import annotations

import numpy as np

from vinu_infra.risk_math import kelly_fraction as _kelly_fraction


def kelly_optimal_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction_of_kelly: float = 1.0,
) -> float:
    """Thin wrapper over vinu_infra.risk_math.kelly_fraction -- the single
    source of truth for this formula (also used by vinu-simulator's
    FractionalKellySizer). Kept as a separate name/module here since
    existing callers import kelly_optimal_fraction from this path."""
    return _kelly_fraction(win_rate, avg_win, avg_loss, fraction_of_kelly)


def risk_budget_position_size(
    risk_budget: float,
    entry_price: float,
    stop_price: float,
    volatility: float | None = None,
    z_score: float = 2.0,
    method: str = "stop_loss",
) -> float:
    if method == "stop_loss":
        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit <= 0:
            return 0.0
        return risk_budget / risk_per_unit
    elif method == "volatility":
        if volatility is None or volatility <= 0:
            return 0.0
        risk_per_unit = entry_price * volatility * z_score
        if risk_per_unit <= 0:
            return 0.0
        return risk_budget / risk_per_unit
    return 0.0


def volatility_parity_weights(
    volatilities: np.ndarray,
) -> np.ndarray:
    valid = volatilities > 0
    if not np.any(valid):
        return np.full_like(volatilities, 1.0 / len(volatilities), dtype=float)
    inv_vol = np.where(valid, 1.0 / volatilities, 0.0)
    total = np.sum(inv_vol)
    if total <= 0:
        return np.full_like(volatilities, 1.0 / len(volatilities), dtype=float)
    return inv_vol / total


def max_position_size_from_risk_budget(
    portfolio_value: float,
    risk_budget_pct: float,
    symbol_volatility: float,
    holding_period_days: int = 1,
    confidence: float = 0.95,
) -> float:
    from scipy import stats as _stats
    z = _stats.norm.ppf((1 + confidence) / 2)
    max_loss_pct = symbol_volatility * z * np.sqrt(holding_period_days / 252)
    if max_loss_pct <= 0:
        return portfolio_value
    max_position = (portfolio_value * risk_budget_pct) / max_loss_pct
    return max(0.0, max_position)
