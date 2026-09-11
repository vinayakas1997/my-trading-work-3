"""Stage C (C9): reason-code / outcome / override-state vocabulary and the
valid-transition set."""

from __future__ import annotations

from vinu_agent.broker.guard_codes import (
    ALLOWED_OVERRIDE_TRANSITIONS,
    OVERRIDE_PRECEDENCE,
    GuardOutcome,
    OverrideState,
    ReasonCode,
    transition_allowed,
)


class TestEnums:
    def test_codes_serialise_as_their_string_value(self) -> None:
        assert ReasonCode.MAX_ORDER_VALUE.value == "max_order_value"
        assert GuardOutcome.PAUSE_FOR_REAUTH == "pause_for_reauth"
        assert OverrideState.REDUCE_ONLY.value == "reduce_only"

    def test_every_reason_code_is_unique(self) -> None:
        values = [c.value for c in ReasonCode]
        assert len(values) == len(set(values))

    def test_override_precedence_is_a_total_order(self) -> None:
        ranks = list(OVERRIDE_PRECEDENCE.values())
        assert len(ranks) == len(set(ranks)) == len(OverrideState)
        # IGNORED (suppresses even the rejection) is the most restrictive
        assert OVERRIDE_PRECEDENCE[OverrideState.IGNORED] == max(ranks)


class TestTransitions:
    def test_clearing_an_override_is_always_allowed(self) -> None:
        for state in list(OverrideState) + [None]:
            assert transition_allowed(state, None) is True

    def test_setting_from_no_override_is_allowed_for_every_state(self) -> None:
        for target in OverrideState:
            assert transition_allowed(None, target) is True

    def test_reduce_only_can_tighten_to_untradeable(self) -> None:
        assert transition_allowed(OverrideState.REDUCE_ONLY, OverrideState.UNTRADEABLE) is True

    def test_a_noop_transition_is_allowed(self) -> None:
        assert transition_allowed(OverrideState.UNTRADEABLE, OverrideState.UNTRADEABLE) is True

    def test_transition_map_covers_every_current_state(self) -> None:
        for state in list(OverrideState) + [None]:
            assert state in ALLOWED_OVERRIDE_TRANSITIONS
