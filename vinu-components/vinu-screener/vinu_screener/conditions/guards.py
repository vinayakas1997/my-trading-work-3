"""Stage B (B2): the non-finite-value guard as a single choke point before
any comparison, crossing, or level-touch check.

Ported verbatim (reasoning included, not just the mechanism) from
FinceptTerminal's `ConditionEvaluator.cpp` (lines 16-22 per the audit):
`math.isnan(inf)` is False, so an `inf` operand (e.g. a percent-change
computed against a zero reference price) would silently satisfy `inf > 70`
and fire a false positive. At ~8000-symbol scale — delisted names, zero
volume, halted trading, gapped price histories — this is not a hypothetical:
some symbol on some day WILL produce inf/-inf/NaN in a ratio-based feature,
and every comparison in the evaluator must refuse to act on it rather than
silently "pass".

`is_finite_operand` is the one function every operand — both sides of a
leaf condition, both the current and the previous-bar reads for crossing
operators — is required to pass through before `evaluator.py` does
anything else with it.
"""

from __future__ import annotations

import math


def is_finite_operand(value: float | None) -> bool:
    """False for None, NaN, +-inf, or anything that doesn't even cast to
    float — i.e. "safe to use in a comparison" is a stricter question than
    "is this a number". Every leaf condition's evaluator gates on this
    before making any decision from the value."""
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def all_finite(*values: float | None) -> bool:
    """Convenience for the multi-operand case (current bar + previous bar
    for crossing operators, both sides of a leaf) — every one of them must
    be finite or the whole leaf is unevaluable."""
    return all(is_finite_operand(v) for v in values)
