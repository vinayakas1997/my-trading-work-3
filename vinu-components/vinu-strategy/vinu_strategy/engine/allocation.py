from __future__ import annotations

import logging
from typing import Any

from vinu_strategy.engine.expression import evaluate_expression, ExpressionError

LOG = logging.getLogger(__name__)


def allocate_equal(candidates: list[str], signals: dict[str, float] | None = None, params: dict[str, Any] | None = None) -> dict[str, float]:
    if not candidates:
        return {}
    w = 1.0 / len(candidates)
    return {sym: w for sym in candidates}


def allocate_signal_scaled(
    candidates: list[str],
    signals: dict[str, float],
    params: dict[str, Any] | None = None,
    signal_context: dict[str, dict[str, Any]] | None = None,
) -> dict[str, float]:
    if not candidates:
        return {}

    signal_expr = (params or {}).get("signal")

    if signal_expr and signal_context:
        return _allocate_by_expression(candidates, signal_expr, signal_context)

    if not signals:
        return allocate_equal(candidates)

    weights = {}
    total_signal = 0.0
    for sym in candidates:
        val = abs(signals.get(sym, 0.0))
        weights[sym] = val
        total_signal += val

    if total_signal <= 0:
        return allocate_equal(candidates, signals, params)

    return {sym: w / total_signal for sym, w in weights.items()}


def _allocate_by_expression(
    candidates: list[str],
    expr: str,
    signal_context: dict[str, dict[str, Any]],
) -> dict[str, float]:
    weights = {}
    total = 0.0
    for sym in candidates:
        ctx = signal_context.get(sym, {}).get("features", {})
        try:
            val = evaluate_expression(expr, ctx)
        except ExpressionError as e:
            LOG.warning("Expression eval failed for '%s': %s", sym, e)
            val = 0.0
        val = val if val is not None else 0.0
        weights[sym] = val
        total += abs(val)

    if total <= 0:
        return allocate_equal(candidates)

    return {sym: w / total for sym, w in weights.items()}


ALLOCATION_METHODS = {
    "equal": allocate_equal,
    "signal_scaled": allocate_signal_scaled,
}


def run_allocation(
    method: str,
    candidates: list[str],
    signals: dict[str, float] | None = None,
    params: dict[str, Any] | None = None,
    signal_context: dict[str, dict[str, Any]] | None = None,
) -> dict[str, float]:
    func = ALLOCATION_METHODS.get(method)
    if func is None:
        LOG.warning("Unknown allocation method '%s', using 'equal'", method)
        return allocate_equal(candidates)
    if method == "signal_scaled":
        return func(candidates, signals, params, signal_context)
    return func(candidates, signals, params)
