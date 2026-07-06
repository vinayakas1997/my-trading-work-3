from __future__ import annotations

import logging
from typing import Any

from vinu_strategy.models.rules import Condition, Action, Rule

LOG = logging.getLogger(__name__)


class RulesEngine:
    def __init__(self, rules_raw: list[dict[str, Any]]):
        self._rules: list[Rule] = []
        for raw in rules_raw:
            try:
                self._rules.append(Rule.from_dict(raw))
            except Exception as e:
                LOG.warning("Failed to load rule %s: %s", raw.get("name", "?"), e)

    def evaluate(self, base_weight: float, signal_context: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
        weight = base_weight
        trace: list[dict[str, Any]] = []
        for rule in self._rules:
            results = self._evaluate_conditions(rule.conditions, signal_context)
            all_met = all(r["met"] for r in results)
            entry: dict[str, Any] = {
                "rule": rule.name,
                "fired": all_met,
                "conditions": results,
            }
            if all_met:
                weight = self._apply_action(rule.action, weight)
                entry["action"] = {
                    "type": rule.action.action if rule.action else None,
                    "value": rule.action.value if rule.action else None,
                }
                entry["weight_after"] = round(weight, 6)
                LOG.debug("Rule '%s' fired: weight -> %.4f", rule.name, weight)
            trace.append(entry)
        return weight, trace

    def _evaluate_conditions(self, conditions: list[Condition], ctx: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for cond in conditions:
            source_data = ctx.get(cond.source, {})
            actual = source_data.get(cond.key)
            met = self._check_condition(cond.operator, actual, cond.value)
            results.append({
                "source": cond.source,
                "key": cond.key,
                "operator": cond.operator,
                "expected": cond.value,
                "actual": actual,
                "met": met,
                "reason": _condition_reason(met, actual, cond.operator, cond.value),
            })
        return results

    def _check_condition(self, op: str, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        try:
            if op == "eq":
                return actual == expected
            elif op == "neq":
                return actual != expected
            elif op == "gt":
                return float(actual) > float(expected)
            elif op == "gte":
                return float(actual) >= float(expected)
            elif op == "lt":
                return float(actual) < float(expected)
            elif op == "lte":
                return float(actual) <= float(expected)
            elif op == "in":
                return actual in (expected or [])
            elif op == "between":
                lo, hi = expected
                return lo <= float(actual) <= hi
            else:
                LOG.warning("Unknown operator '%s'", op)
                return False
        except (TypeError, ValueError) as e:
            LOG.warning("Condition eval error: %s", e)
            return False

    def _apply_action(self, action: Action | None, current_weight: float) -> float:
        if action is None:
            return current_weight
        try:
            if action.action == "weight_add":
                return current_weight + action.value
            elif action.action == "weight_subtract":
                return current_weight - action.value
            elif action.action == "weight_multiply":
                return current_weight * action.value
            elif action.action == "weight_set":
                return action.value
            return current_weight
        except Exception as e:
            LOG.warning("Action error: %s", e)
            return current_weight


def _condition_reason(met: bool, actual: Any, op: str, expected: Any) -> str:
    if met:
        return f"PASS: actual={actual} {op} {expected}"
    if actual is None:
        return f"FAIL: key not found in context"
    return f"FAIL: actual={actual} does not satisfy {op} {expected}"
