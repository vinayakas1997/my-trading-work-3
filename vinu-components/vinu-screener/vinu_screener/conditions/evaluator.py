"""The glue between B1 (schema), B2 (non-finite guard), and B4/B5 (feature
library): evaluates a parsed condition tree against one symbol's OHLCV
frame. This is what B6's scan loop calls per symbol per cycle.

Every operand — both sides of a leaf, and the previous-bar reads crossing/
direction/level-touch operators need — goes through
`guards.is_finite_operand` before any decision is made from it. A leaf
that can't be evaluated (non-finite operand, insufficient history) returns
False, never raises and never silently "passes" — a rule failing open on
bad data would be far worse here than a rule just not firing this cycle.
"""

from __future__ import annotations

import pandas as pd

from ..features.library import FeatureLibrary
from .guards import is_finite_operand
from .schema import ConditionGroup, ConditionLeaf, ConditionNode

# Operators whose current-bar-only reading uses simple numeric comparison.
_SIMPLE_OPS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}

_LEVEL_TOUCH_RELATIVE_TOL = 1e-7
_LEVEL_TOUCH_ABS_FLOOR = 1e-9


def _level_touch(lhs: float, rhs: float, prev_lhs: float | None, prev_rhs: float | None) -> bool:
    """Float-tolerant `==`: fires when the two are within a relative
    tolerance of each other, OR when the sign of (lhs - rhs) flipped since
    the previous sample — i.e. the price crossed through the level between
    two polls even though it never landed exactly on it. Directly answers
    "how do I detect a level cross with discrete (non-tick) polling"."""
    tol = max(abs(rhs) * _LEVEL_TOUCH_RELATIVE_TOL, _LEVEL_TOUCH_ABS_FLOOR)
    if abs(lhs - rhs) <= tol:
        return True
    if prev_lhs is None or prev_rhs is None:
        return False
    if not is_finite_operand(prev_lhs) or not is_finite_operand(prev_rhs):
        return False
    return (prev_lhs - prev_rhs) * (lhs - rhs) < 0.0


def _resolve_operand(
    ohlcv: pd.DataFrame,
    library: FeatureLibrary,
    symbol: str,
    indicator: str,
    params: dict,
    field_name: str,
    offset: int,
) -> float | None:
    try:
        result = library.compute(symbol, ohlcv, indicator, params)
        series = library.field(result, field_name)
    except KeyError:
        return None
    if offset >= len(series):
        return None
    val = series.iloc[-1 - offset]
    return float(val) if pd.notna(val) else None


def evaluate_leaf(leaf: ConditionLeaf, ohlcv: pd.DataFrame, library: FeatureLibrary, symbol: str) -> bool:
    lhs = _resolve_operand(ohlcv, library, symbol, leaf.indicator, leaf.params, leaf.field_name, leaf.offset)
    if leaf.compare_mode == "indicator":
        rhs = _resolve_operand(
            ohlcv, library, symbol, leaf.compare_indicator, leaf.compare_params,
            leaf.compare_field, leaf.compare_offset,
        )
    else:
        rhs = leaf.value

    if leaf.operator in ("crosses_above", "crosses_below", "rising", "falling", "==", "!="):
        prev_lhs = _resolve_operand(
            ohlcv, library, symbol, leaf.indicator, leaf.params, leaf.field_name, leaf.offset + 1,
        )
        prev_rhs = (
            _resolve_operand(
                ohlcv, library, symbol, leaf.compare_indicator, leaf.compare_params,
                leaf.compare_field, leaf.compare_offset + 1,
            )
            if leaf.compare_mode == "indicator" else rhs
        )
    else:
        prev_lhs = prev_rhs = None

    if not is_finite_operand(lhs) or not is_finite_operand(rhs):
        return False

    op = leaf.operator
    if op in _SIMPLE_OPS:
        return bool(_SIMPLE_OPS[op](lhs, rhs))
    if op == "==":
        return _level_touch(lhs, rhs, prev_lhs, prev_rhs)
    if op == "!=":
        return not _level_touch(lhs, rhs, prev_lhs, prev_rhs)
    # crossing / direction operators genuinely need the previous bar
    if not is_finite_operand(prev_lhs) or (leaf.compare_mode == "indicator" and not is_finite_operand(prev_rhs)):
        return False
    if op == "crosses_above":
        return prev_lhs <= prev_rhs and lhs > rhs
    if op == "crosses_below":
        return prev_lhs >= prev_rhs and lhs < rhs
    if op == "rising":
        return lhs > prev_lhs
    if op == "falling":
        return lhs < prev_lhs
    raise ValueError(f"unhandled operator {op!r}")  # unreachable: schema validates operator membership


def evaluate(node: ConditionNode, ohlcv: pd.DataFrame, library: FeatureLibrary, symbol: str) -> bool:
    """Evaluate a full condition tree (leaf or group) against one symbol's
    OHLCV frame. AND/OR short-circuit."""
    if isinstance(node, ConditionLeaf):
        return evaluate_leaf(node, ohlcv, library, symbol)
    result = _evaluate_group(node, ohlcv, library, symbol)
    return (not result) if node.negate else result


def _evaluate_group(group: ConditionGroup, ohlcv: pd.DataFrame, library: FeatureLibrary, symbol: str) -> bool:
    if group.logic == "AND":
        for child in group.children:
            if not evaluate(child, ohlcv, library, symbol):
                return False
        return True
    for child in group.children:
        if evaluate(child, ohlcv, library, symbol):
            return True
    return False
