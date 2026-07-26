from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from vinu_live.book.positions import BookBackend, list_open_positions
from vinu_live.book.exposure import (
    portfolio_total_exposure,
    portfolio_gross_exposure,
    per_symbol_exposure,
)
from vinu_live.breaker.limits import BreakerLimits, BreakerState, DEFAULT_LIMITS

LOG = logging.getLogger(__name__)


class BreakerVerdict:
    ALLOW = "ALLOW"
    HALT = "HALT"


def _check_daily_loss(
    daily_realized_pnl: float,
    portfolio_value: float,
    limits: BreakerLimits,
) -> str | None:
    if portfolio_value <= 0:
        return None
    loss_pct = abs(min(daily_realized_pnl, 0)) / portfolio_value
    if loss_pct >= limits.max_daily_loss_pct:
        return (
            f"Daily loss {loss_pct:.1%} exceeds limit {limits.max_daily_loss_pct:.1%}"
        )
    return None


def _check_aggregate_var(
    positions: list,
    prices: dict[str, float],
    covariance_matrix: np.ndarray | None,
    limits: BreakerLimits,
) -> str | None:
    if covariance_matrix is None:
        return None

    symbols = sorted({p.symbol for p in positions if p.symbol in prices})
    if len(symbols) < 2:
        return None

    idx_map = {s: i for i, s in enumerate(symbols)}
    weights = np.zeros(len(symbols))
    total_value = sum(p.qty * prices.get(p.symbol, 0) for p in positions)
    if total_value <= 0:
        return None

    for p in positions:
        price = prices.get(p.symbol)
        if price is None:
            continue
        i = idx_map.get(p.symbol)
        if i is None:
            continue
        weights[i] = p.qty * price / total_value

    portfolio_var = float(np.dot(weights.T, np.dot(covariance_matrix, weights)))
    portfolio_vol = np.sqrt(max(portfolio_var, 1e-12))
    from scipy import stats as _stats
    var_95 = float(_stats.norm.ppf(0.05) * portfolio_vol)

    if abs(var_95) > limits.max_var_95_pct:
        return (
            f"Aggregate VaR(95%) {abs(var_95):.1%} exceeds limit "
            f"{limits.max_var_95_pct:.1%}"
        )
    return None


def _check_position_count(
    positions: list,
    limits: BreakerLimits,
) -> str | None:
    if len(positions) > limits.max_position_count:
        return (
            f"Position count {len(positions)} exceeds limit "
            f"{limits.max_position_count}"
        )
    return None


def _check_cluster_exposure(
    positions: list,
    prices: dict[str, float],
    cluster_map: dict[str, str] | None,
    limits: BreakerLimits,
) -> str | None:
    if not cluster_map:
        return None
    total = portfolio_total_exposure(positions, prices)
    if total == 0:
        return None
    cluster_exposure: dict[str, float] = {}
    for p in positions:
        price = prices.get(p.symbol)
        if price is None:
            continue
        cluster = cluster_map.get(p.symbol, "other")
        value = p.qty * price * (1 if p.side == "long" else -1)
        cluster_exposure[cluster] = cluster_exposure.get(cluster, 0.0) + abs(value)
    for cluster, exposure in cluster_exposure.items():
        pct = exposure / abs(total)
        if pct > limits.max_cluster_exposure_pct and cluster != "other":
            return (
                f"Cluster '{cluster}' exposure {pct:.1%} exceeds limit "
                f"{limits.max_cluster_exposure_pct:.1%}"
            )
    return None


def _check_leverage(
    positions: list,
    prices: dict[str, float],
    portfolio_value: float,
    limits: BreakerLimits,
) -> str | None:
    if portfolio_value <= 0:
        return None
    gross = portfolio_gross_exposure(positions, prices)
    leverage = gross / portfolio_value
    if leverage > limits.max_leverage:
        return (
            f"Leverage {leverage:.2f}x exceeds limit {limits.max_leverage:.2f}x"
        )
    return None


def check_limits(
    backend: BookBackend,
    prices: dict[str, float],
    portfolio_value: float,
    daily_realized_pnl: float,
    covariance_matrix: np.ndarray | None = None,
    cluster_map: dict[str, str] | None = None,
    limits: BreakerLimits | None = None,
    state: BreakerState | None = None,
) -> tuple[str, str | None]:
    limits = limits or DEFAULT_LIMITS
    state = state or BreakerState()

    if state.halted:
        return BreakerVerdict.HALT, state.halted_reason

    positions = list_open_positions(backend)

    checks = [
        ("daily_loss", _check_daily_loss(daily_realized_pnl, portfolio_value, limits)),
        ("aggregate_var", _check_aggregate_var(positions, prices, covariance_matrix, limits)),
        ("position_count", _check_position_count(positions, limits)),
        ("cluster_exposure", _check_cluster_exposure(positions, prices, cluster_map, limits)),
        ("leverage", _check_leverage(positions, prices, portfolio_value, limits)),
    ]

    for name, reason in checks:
        if reason is not None:
            LOG.warning("Breaker HALT: %s — %s", name, reason)
            state.halted = True
            state.halted_at = datetime.now(timezone.utc).isoformat()
            state.halted_reason = reason
            return BreakerVerdict.HALT, reason

    return BreakerVerdict.ALLOW, None


def reset_breaker(state: BreakerState) -> None:
    LOG.info("Breaker reset by explicit action")
    state.reset()
