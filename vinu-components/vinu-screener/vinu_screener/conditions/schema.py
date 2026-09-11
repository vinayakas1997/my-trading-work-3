"""Stage B (B1): the condition JSON schema everything else in `vinu-screener`
evaluates against. Ported wholesale from FinceptTerminal's `ConditionEvaluator`
(see other-repos-world/comprison-other-vinu/13-fincept-terminal.md) — the
cleanest condition-schema reference audited, and (per that repo's own
comments) already hardened against real messy-market-data failure modes.

A condition node is either:
  - a **leaf**: one comparison, `{indicator, params, field, offset, operator,
    compare_mode, value | compare_indicator/compare_params/compare_field/
    compare_offset}` — e.g. "RSI(14) 3 bars ago > 70", or "close crosses_above
    its own SMA(20)" (compare_mode="indicator" makes the right-hand side a
    second indicator lookup instead of a literal).
  - a **group**: `{children, logic, negate}` — AND/OR over child nodes
    (leaves or nested groups), with short-circuit evaluation, so a rule can
    express `(A AND B) OR C` without a second rule type.

This module only defines and *parses* the schema (dataclasses + validation);
evaluating a tree against real data is `evaluator.py` (which uses B2's
non-finite guard and calls out to a `FeatureLibrary` for B4/B5's actual
indicator math) — kept separate so the schema has zero data dependencies
and is trivially serialisable to/from the JSON a rule is stored as.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

# Operators requiring only the current bar's value(s).
SIMPLE_OPERATORS = frozenset({">", "<", ">=", "<=", "==", "!="})
# Operators that inherently compare against the previous bar too (the
# evaluator reads one extra bar back for these automatically — B1's
# `op_needs_prev`, so callers never have to know).
PREV_BAR_OPERATORS = frozenset({"crosses_above", "crosses_below", "rising", "falling"})
OPERATORS = SIMPLE_OPERATORS | PREV_BAR_OPERATORS

COMPARE_MODES = frozenset({"value", "indicator"})
LOGIC_MODES = frozenset({"AND", "OR"})


class ConditionSchemaError(ValueError):
    """A condition node's JSON doesn't satisfy the schema."""


def op_needs_prev(operator: str) -> bool:
    """True for operators the evaluator must read one extra bar back for
    (crossing / direction operators) — B1's `op_needs_prev`."""
    return operator in PREV_BAR_OPERATORS


@dataclass(frozen=True)
class ConditionLeaf:
    """One comparison. The left-hand operand is always an indicator lookup
    (`indicator`/`params`/`field`/`offset`); the right-hand side is either a
    literal (`compare_mode="value"`, read from `value`) or a second
    indicator lookup (`compare_mode="indicator"`, read from
    `compare_indicator`/`compare_params`/`compare_field`/`compare_offset`)."""

    indicator: str
    operator: str
    params: dict[str, Any] = field(default_factory=dict)
    field_name: str = "value"          # which output column, for multi-output indicators (e.g. MACD's "signal")
    offset: int = 0                    # bars ago for the left-hand operand
    compare_mode: str = "value"
    value: float | None = None
    compare_indicator: str | None = None
    compare_params: dict[str, Any] = field(default_factory=dict)
    compare_field: str = "value"
    compare_offset: int = 0

    def __post_init__(self) -> None:
        if not self.indicator or not isinstance(self.indicator, str):
            raise ConditionSchemaError("leaf.indicator must be a non-empty string")
        if self.operator not in OPERATORS:
            raise ConditionSchemaError(f"leaf.operator {self.operator!r} is not one of {sorted(OPERATORS)}")
        if self.compare_mode not in COMPARE_MODES:
            raise ConditionSchemaError(f"leaf.compare_mode {self.compare_mode!r} is not one of {sorted(COMPARE_MODES)}")
        if self.offset < 0 or self.compare_offset < 0:
            raise ConditionSchemaError("offset / compare_offset must be >= 0 (bars ago, not bars ahead)")
        if self.compare_mode == "value" and self.value is None:
            raise ConditionSchemaError("compare_mode='value' requires a numeric `value`")
        if self.compare_mode == "indicator" and not self.compare_indicator:
            raise ConditionSchemaError("compare_mode='indicator' requires `compare_indicator`")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ConditionLeaf":
        try:
            return cls(
                indicator=raw["indicator"],
                operator=raw["operator"],
                params=dict(raw.get("params") or {}),
                field_name=raw.get("field", "value"),
                offset=int(raw.get("offset", 0)),
                compare_mode=raw.get("compare_mode", "value"),
                value=(float(raw["value"]) if raw.get("value") is not None else None),
                compare_indicator=raw.get("compare_indicator"),
                compare_params=dict(raw.get("compare_params") or {}),
                compare_field=raw.get("compare_field", "value"),
                compare_offset=int(raw.get("compare_offset", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConditionSchemaError(f"malformed leaf condition: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator,
            "operator": self.operator,
            "params": self.params,
            "field": self.field_name,
            "offset": self.offset,
            "compare_mode": self.compare_mode,
            "value": self.value,
            "compare_indicator": self.compare_indicator,
            "compare_params": self.compare_params,
            "compare_field": self.compare_field,
            "compare_offset": self.compare_offset,
        }


@dataclass(frozen=True)
class ConditionGroup:
    """AND/OR over child nodes (leaves or nested groups), with an optional
    `negate` applied to the group's own result."""

    children: tuple["ConditionNode", ...]
    logic: str = "AND"
    negate: bool = False

    def __post_init__(self) -> None:
        if self.logic not in LOGIC_MODES:
            raise ConditionSchemaError(f"group.logic {self.logic!r} is not one of {sorted(LOGIC_MODES)}")
        if not self.children:
            raise ConditionSchemaError("group.children must not be empty")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ConditionGroup":
        try:
            children = tuple(parse_condition(c) for c in raw["children"])
        except (KeyError, TypeError) as exc:
            raise ConditionSchemaError(f"malformed group condition: {exc}") from exc
        return cls(children=children, logic=raw.get("logic", "AND"), negate=bool(raw.get("negate", False)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "children": [c.to_dict() for c in self.children],
            "logic": self.logic,
            "negate": self.negate,
        }


ConditionNode = Union[ConditionLeaf, ConditionGroup]


def parse_condition(raw: Any) -> ConditionNode:
    """Parse one JSON-shaped condition node (leaf or group), recursively.

    Backward-compatible with a **flat list of leaves** (the legacy schema
    FinceptTerminal itself stayed compatible with) — a bare `[leaf, leaf,
    ...]` is treated as an implicit top-level AND group, so callers never
    have to special-case "old rules that predate groups"."""
    if isinstance(raw, list):
        if not raw:
            raise ConditionSchemaError("a flat condition list must not be empty")
        return ConditionGroup(children=tuple(parse_condition(c) for c in raw), logic="AND", negate=False)
    if not isinstance(raw, dict):
        raise ConditionSchemaError(f"condition node must be a dict or list, got {type(raw).__name__}")
    if "children" in raw:
        return ConditionGroup.from_dict(raw)
    return ConditionLeaf.from_dict(raw)


def walk(node: ConditionNode):
    """Yield every leaf in the tree, depth-first — the one traversal B2's
    guard placement, B3's lookback calc, and any future rule-linter all
    build on, so there's a single definition of "every leaf in this rule"."""
    if isinstance(node, ConditionLeaf):
        yield node
    else:
        for child in node.children:
            yield from walk(child)
