"""Mechanical evaluation of Phase 4's frozen contingency/invalidation rules.

Every rule on a frozen TradePlan is a `metric`/`operator`/`threshold` triple (see
`vinu_research.models.ContingencyRule`/`InvalidationCondition`) -- this module is the Phase 6
half of that contract: it evaluates the triple against a live metric value and returns a
decision, never interprets free text. `vinu-live` deliberately does not import
`vinu_research.models` (see Phase 6 design decision #2) -- rules arrive here as plain dicts
parsed from the artifact's `trade_plan_data` JSON, and this module re-validates the operator
set independently rather than trusting the upstream service did.
"""

from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)

_OPERATORS: dict[str, Any] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def evaluate_condition(value: float, operator: str, threshold: float) -> bool:
    """True if `value operator threshold` holds. Unknown operators never trigger."""
    op = _OPERATORS.get(operator)
    if op is None:
        LOG.warning("Unknown operator %r in rule -- treating as not-triggered", operator)
        return False
    return bool(op(value, threshold))


def find_triggered_rules(
    rules: list[dict[str, Any]],
    live_metrics: dict[str, float],
) -> list[dict[str, Any]]:
    """Return the subset of `rules` whose metric/operator/threshold currently holds.

    A rule referencing a metric absent from `live_metrics` never triggers (missing data is
    not treated as satisfying a condition) and is logged, not silently skipped.
    """
    triggered: list[dict[str, Any]] = []
    for rule in rules:
        metric = rule.get("metric")
        operator = rule.get("operator")
        threshold = rule.get("threshold")
        if metric not in live_metrics:
            LOG.debug("Rule metric %r not in live metrics -- skipping (not triggered)", metric)
            continue
        if evaluate_condition(live_metrics[metric], operator, threshold):
            triggered.append(rule)
    return triggered
