from __future__ import annotations

import logging
from typing import Any

from vinu_strategy.engine.rules_engine import RulesEngine

LOG = logging.getLogger(__name__)


def timing_none(weights: dict[str, float], signal_context: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
    return weights, {}


def timing_rules(weights: dict[str, float], signal_context: dict[str, Any], params: dict[str, Any] | None = None) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
    rules_raw = (params or {}).get("rules", [])
    trace: dict[str, list[dict[str, Any]]] = {}
    if not rules_raw:
        return weights, trace
    engine = RulesEngine(rules_raw)
    adjusted = {}
    for sym, w in weights.items():
        ctx = signal_context.get(sym, {}) if signal_context else {}
        adjusted[sym], sym_trace = engine.evaluate(w, ctx)
        if sym_trace:
            trace[sym] = sym_trace
    return adjusted, trace


TIMING_METHODS = {
    "none": timing_none,
    "rules": timing_rules,
}


def run_timing(method: str, weights: dict[str, float], signal_context: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
    func = TIMING_METHODS.get(method)
    if func is None:
        LOG.warning("Unknown timing method '%s', using 'none'", method)
        return weights, {}
    return func(weights, signal_context, params)
