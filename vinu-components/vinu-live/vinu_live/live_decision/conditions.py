"""Must-condition / confirmation-condition evaluation.

Reuses the exact {source, key, operator, value} vocabulary already
established by vinu-strategy's Condition/RulesEngine
(vinu_strategy/models/rules.py, vinu_strategy/engine/rules_engine.py) --
same operator set (eq/neq/gt/gte/lt/lte/in/between), same nested-key
lookup -- rather than inventing a second condition DSL for the live
decision loop. Implemented locally in vinu-live rather than importing
vinu_strategy directly: services in this codebase talk to each other
over HTTP, not shared Python imports (confirmed convention -- every
cross-service call cited across missing-pieces-of-system/new-theory-of-
trading goes through an HTTP client, never a direct import of another
service's package).

Design reference: .../reverse-engineering/03-poller-and-state-schema.md
Part B step 2 ("the exact must-condition/confirmation-condition
evaluation engine... left open"), resolved here.
"""

from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)

_OPERATORS = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "in", "between"})


def _lookup(ctx: dict[str, dict[str, Any]], source: str, key: str) -> Any:
    source_data = ctx.get(source, {})
    actual: Any = source_data
    for part in key.split("."):
        if not isinstance(actual, dict) or part not in actual:
            return None
        actual = actual[part]
    return actual


def _check(op: str, actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    try:
        if op == "eq":
            return actual == expected
        if op == "neq":
            return actual != expected
        if op == "gt":
            return float(actual) > float(expected)
        if op == "gte":
            return float(actual) >= float(expected)
        if op == "lt":
            return float(actual) < float(expected)
        if op == "lte":
            return float(actual) <= float(expected)
        if op == "in":
            return actual in (expected or [])
        if op == "between":
            lo, hi = expected
            return lo <= float(actual) <= hi
        LOG.warning("Unknown condition operator %r", op)
        return False
    except (TypeError, ValueError) as exc:
        LOG.warning("Condition eval error (op=%s, actual=%r, expected=%r): %s", op, actual, expected, exc)
        return False


def evaluate_all(
    conditions: list[dict[str, Any]],
    ctx: dict[str, dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    """Hard AND over every condition -- all() semantics matching
    00-explanation.md Layer 1: "every must-condition in this layer is a
    hard AND, no exceptions, no scoring." Same shape used for
    confirmation_conditions too (Part B step 3), just called at a
    different stage of the state machine.

    `ctx` is keyed by source ("live_indicators", "features",
    "correlation", ...) -- for the live decision loop, callers pass
    {"live_indicators": <point 3's snapshot dict>}.

    Returns (all_met, per-condition trace) -- the trace is for
    strategy_stage_transitions.reason / debugging, not stored as its own
    column (keeps the transitions table's shape stable regardless of how
    many conditions a strategy declares).
    """
    if not conditions:
        return False, []
    results: list[dict[str, Any]] = []
    for cond in conditions:
        source = cond.get("source", "live_indicators")
        key = cond["key"]
        op = cond.get("operator", "gt")
        expected = cond.get("value")
        actual = _lookup(ctx, source, key)
        met = _check(op, actual, expected)
        results.append({
            "source": source, "key": key, "operator": op,
            "expected": expected, "actual": actual, "met": met,
        })
    return all(r["met"] for r in results), results


def condition_name(condition: dict[str, Any]) -> str:
    """Deterministic string identity for a must-condition -- item #16's
    SignalEvidenceStore (vinu-research, Phase 2) needs a string name per
    condition (`record_trigger`'s `must_condition: str | list[str]`), but
    the real, implemented condition vocabulary here is the structured
    {source, key, operator, value} dict above, with no name field.
    Confirmed directly (2026-09-28): auto-derive rather than require an
    authored `name:` in every strategy's YAML -- every existing
    strategy gets a real, usable name for free, no file needs editing.
    Not the same as `03-strategy-definition-full-schema.md`'s still-
    design-only `condition: "sma5_cross_sma50"` field -- that would be a
    human-authored label on a not-yet-built schema; this is a mechanical
    derivation from what's actually implemented today.

    The rule itself lives in `vinu_infra.condition_names` so the agent's evidence filter uses the very same one."""
    from vinu_infra.condition_names import condition_name as _shared

    return _shared(condition)
