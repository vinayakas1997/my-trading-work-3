"""Phase 2: classify_action() overlays the high-expectations spec's
HOLD/ADD/REDUCE/EXIT 4-way outcome onto orchestrator.py's own much richer
action-string vocabulary, without replacing or rewriting it.

The table-driven test below scans the orchestrator source for every
`"action": "<literal>"` string this module can actually emit and asserts
each has an explicit entry in _ACTION_CLASS_MAP -- so a new, unmapped action
string added later fails this test instead of silently defaulting to HOLD.
"""

from __future__ import annotations

import inspect
import re

from vinu_live.trade_plan import orchestrator
from vinu_live.trade_plan.orchestrator import _ACTION_CLASS_MAP, classify_action

_VALID_CLASSES = {"HOLD", "ADD", "REDUCE", "EXIT"}

# Matches `"action": "literal_string"` -- the shape every cycle-result dict
# in orchestrator.py uses for its own emitted action strings. Deliberately
# does not match `"action": corr.get(...)` / `result["action"] = OOD_...`
# dynamic assignments, which reference values already covered by their own
# literal-producing call sites elsewhere in the file.
_ACTION_LITERAL_RE = re.compile(r'"action":\s*"([a-z_]+)"')


def _all_action_literals() -> set[str]:
    source = inspect.getsource(orchestrator)
    return set(_ACTION_LITERAL_RE.findall(source))


class TestActionClassMapCompleteness:
    def test_every_action_literal_in_source_has_a_mapping(self) -> None:
        literals = _all_action_literals()
        assert literals, "regex found no action literals -- likely means the pattern is stale"
        unmapped = literals - set(_ACTION_CLASS_MAP)
        assert not unmapped, (
            f"orchestrator.py emits action string(s) {sorted(unmapped)} with no entry in "
            "_ACTION_CLASS_MAP -- add an explicit HOLD/ADD/REDUCE/EXIT classification"
        )

    def test_every_mapped_value_is_a_valid_trade_action(self) -> None:
        for action, cls in _ACTION_CLASS_MAP.items():
            assert cls in _VALID_CLASSES, f"{action!r} maps to invalid class {cls!r}"


class TestClassifyAction:
    def test_entered_is_add(self) -> None:
        assert classify_action("entered") == "ADD"

    def test_hold_is_hold(self) -> None:
        assert classify_action("hold") == "HOLD"

    def test_invalidation_exit_is_exit(self) -> None:
        assert classify_action("invalidation_exit") == "EXIT"

    def test_emergency_flatten_is_exit(self) -> None:
        assert classify_action("emergency_flatten") == "EXIT"

    def test_reduce_position_is_reduce(self) -> None:
        assert classify_action("reduce_position") == "REDUCE"

    def test_tighten_stop_is_reduce(self) -> None:
        assert classify_action("tighten_stop") == "REDUCE"

    def test_unfilled_variants_are_hold(self) -> None:
        for action in ("entry_not_filled", "exit_not_filled", "reduce_not_filled", "rebalance_not_filled"):
            assert classify_action(action) == "HOLD"

    def test_unknown_action_defaults_to_hold(self) -> None:
        assert classify_action("some_future_action_nobody_mapped_yet") == "HOLD"
