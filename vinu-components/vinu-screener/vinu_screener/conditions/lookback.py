"""Stage B (B3): auto-computed required lookback from a condition tree.

Ported from FinceptTerminal's `RealtimeScanRunner::required_bars()`:
recursively walk the condition tree and compute, per leaf,
``max(indicator_period, compare_indicator_period) + max(offset,
compare_offset) + 2`` (the fixed `+2` margin covers the one-extra-bar-back
crossing/direction operators need), then take the max across every leaf in
the tree — floored at 2. This is how much warm-up history a symbol needs
before a rule is even eligible to evaluate against it; a scanner over
~8000 heterogeneous symbols (fresh IPOs, sparse history, halted names)
will constantly have candidates below this bar, and evaluating a rule on
a truncated window rather than marking it "not warmed yet" is exactly the
kind of bug this calculation exists to prevent.
"""

from __future__ import annotations

from typing import Any

from .schema import ConditionLeaf, ConditionNode, op_needs_prev, walk

# Keys inside a leaf's `params`/`compare_params` that name a lookback
# period. Deliberately over-inclusive (checks every key that plausibly
# means "how many bars back does this indicator look") rather than a fixed
# per-indicator-name table, so a new indicator with a `period`/`window`/
# `span` parameter is covered automatically without editing this module.
_PERIOD_KEYS = (
    "period", "span", "window", "n", "length",
    "fast", "slow", "fast_period", "slow_period", "signal_period",
)

MIN_REQUIRED_BARS = 2


def _period_of(params: dict[str, Any]) -> int:
    candidates = []
    for key, val in (params or {}).items():
        if key in _PERIOD_KEYS and isinstance(val, (int, float)) and not isinstance(val, bool):
            candidates.append(int(val))
    return max(candidates, default=1)


def leaf_required_bars(leaf: ConditionLeaf) -> int:
    own_period = _period_of(leaf.params)
    compare_period = _period_of(leaf.compare_params) if leaf.compare_mode == "indicator" else 1
    max_offset = max(leaf.offset, leaf.compare_offset)
    bars = max(own_period, compare_period) + max_offset + 2
    return max(bars, MIN_REQUIRED_BARS)


def required_bars(node: ConditionNode) -> int:
    """The warm-up buffer size (in bars) a symbol needs before this whole
    rule tree is safe to evaluate against it."""
    return max((leaf_required_bars(leaf) for leaf in walk(node)), default=MIN_REQUIRED_BARS)
