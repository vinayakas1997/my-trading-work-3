from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


_OPERATORS = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "in", "between"})


@dataclass
class Condition:
    # "live_indicators" added for the live-decision-loop's must-condition/
    # confirmation-condition checks (missing-pieces-of-system/new-theory-
    # of-trading/system-wide-audit-and-design/reverse-engineering/
    # 03-poller-and-state-schema.md) -- same {source, key, operator, value}
    # shape as the existing weight-rule conditions, reused rather than a
    # new condition DSL invented for the live-decision loop.
    source: Literal["features", "correlation", "live_indicators"]
    key: str
    operator: str = "gt"
    value: Any = None

    @classmethod
    def from_dict(cls, d: dict) -> Condition:
        op_keys = [k for k in d if k in _OPERATORS]
        op = op_keys[0] if op_keys else "eq"
        value = d.get(op)
        return cls(
            source=d.get("source", "features"),
            key=d["key"],
            operator=op,
            value=value,
        )


@dataclass
class Action:
    action: Literal["weight_add", "weight_subtract", "weight_multiply", "weight_set"]
    value: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> Action:
        return cls(action=d["action"], value=d.get("value", 0.0))


@dataclass
class Rule:
    name: str
    conditions: list[Condition] = field(default_factory=list)
    action: Action | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Rule:
        raw_conditions = d.get("when", [])
        return cls(
            name=d["name"],
            conditions=[Condition.from_dict(c) for c in raw_conditions],
            action=Action.from_dict(d["then"]) if "then" in d else None,
        )
