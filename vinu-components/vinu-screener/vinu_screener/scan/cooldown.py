"""Stage B (B8): edge-gated, per-(rule, symbol) cooldown firing.

Ported from FinceptTerminal's `ScanMonitor`/`RealtimeScanRunner`, which
share this exact mechanism regardless of execution mode: a rule that stays
true for many consecutive cycles must fire once on the false->true
transition, not every cycle it remains true (that's the "edge gate" —
`armed` tracks whether the condition was already true last time this
symbol was checked); on top of that, `cooldown_min` enforces a minimum
gap between two *fires*, so a rule that flickers true/false/true across
noisy data still can't spam faster than the cooldown even though each
flip is technically a fresh edge.

Per-(rule_id, symbol) state, kept in memory in `CooldownGate` for now —
the plan's B17 (fired-watch audit retention split, Phase B-4) is where a
permanent history table gets added; this module is only the live gating
decision, not the audit trail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FireState:
    prev_condition: bool = False
    last_fired_at: float | None = None


class CooldownGate:
    def __init__(self) -> None:
        self._state: dict[tuple[str, str], FireState] = {}

    def should_fire(
        self,
        rule_id: str,
        symbol: str,
        condition_true: bool,
        cooldown_min: float,
        *,
        now: float | None = None,
    ) -> bool:
        """True exactly when this call represents a fresh false->true edge
        for this (rule, symbol) pair AND at least `cooldown_min` minutes
        have passed since the last time it fired. Always updates the
        tracked previous-condition state, whether or not it fires — a
        caller that stops calling `should_fire` for a symbol (e.g. it drops
        out of the coarse-filtered universe for a cycle) just means that
        symbol's edge state goes stale, which is the correct behaviour: the
        next time it reappears and is true, that's a fresh edge again."""
        now = now if now is not None else time.time()
        key = (rule_id, symbol)
        st = self._state.setdefault(key, FireState())

        is_edge = condition_true and not st.prev_condition
        st.prev_condition = condition_true

        if not is_edge:
            return False
        if st.last_fired_at is not None and (now - st.last_fired_at) < cooldown_min * 60.0:
            return False
        st.last_fired_at = now
        return True

    def reset(self, rule_id: str, symbol: str | None = None) -> None:
        """Clear tracked state -- for one symbol under a rule, or every
        symbol under it (e.g. the rule was just edited/re-enabled and
        shouldn't inherit stale armed/cooldown state from before the edit)."""
        if symbol is not None:
            self._state.pop((rule_id, symbol), None)
            return
        for key in [k for k in self._state if k[0] == rule_id]:
            self._state.pop(key, None)

    def state_of(self, rule_id: str, symbol: str) -> FireState | None:
        return self._state.get((rule_id, symbol))
