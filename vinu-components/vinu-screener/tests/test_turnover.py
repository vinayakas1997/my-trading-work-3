from __future__ import annotations

from vinu_screener.pipeline.turnover import TurnoverConfig, TurnoverState, apply_turnover_gate


class TestFirstCycle:
    def test_first_cycle_admits_top_n(self) -> None:
        state = TurnoverState()
        held = apply_turnover_gate(["A", "B", "C", "D"], state, TurnoverConfig(top_n=2))
        assert held == ["A", "B"]
        assert state.hold_cycles == {"A": 1, "B": 1}


class TestHoldThresh:
    def test_symbol_not_yet_past_hold_thresh_is_kept_even_if_ranked_out(self) -> None:
        state = TurnoverState()
        apply_turnover_gate(["A", "B"], state, TurnoverConfig(top_n=2, hold_thresh=3))
        # A, B ranked out next cycle by C, D -- but hold_thresh=3 keeps them (only 1 cycle held so far)
        held = apply_turnover_gate(["C", "D", "A", "B"], state, TurnoverConfig(top_n=2, hold_thresh=3))
        assert set(held) == {"A", "B"}

    def test_symbol_past_hold_thresh_can_be_dropped(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=2, hold_thresh=2)
        apply_turnover_gate(["A", "B"], state, cfg)          # cycle 1: A,B held=1
        apply_turnover_gate(["A", "B"], state, cfg)          # cycle 2: A,B held=2 (past thresh)
        held = apply_turnover_gate(["C", "D"], state, cfg)   # cycle 3: A,B rank out, eligible to drop
        assert set(held) == {"C", "D"}


class TestNDrop:
    def test_n_drop_caps_drops_per_cycle(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=4, n_drop=1, hold_thresh=0)
        apply_turnover_gate(["A", "B", "C", "D"], state, cfg)
        held = apply_turnover_gate(["E", "F", "G", "H"], state, cfg)
        # only 1 of A/B/C/D may be dropped this cycle
        survivors_from_first = set(held) & {"A", "B", "C", "D"}
        assert len(survivors_from_first) == 3

    def test_n_drop_none_drops_as_many_as_fresh_ranking_wants(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=2, n_drop=None, hold_thresh=0)
        apply_turnover_gate(["A", "B"], state, cfg)
        held = apply_turnover_gate(["C", "D"], state, cfg)
        assert set(held) == {"C", "D"}


class TestFreeSlotsFilledFromFreshRanking:
    def test_dropped_slot_is_filled_by_best_available_new_candidate(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=2, n_drop=1, hold_thresh=0)
        apply_turnover_gate(["A", "B"], state, cfg)
        held = apply_turnover_gate(["C", "A"], state, cfg)  # B ranked out, A stays, C fills the slot
        assert set(held) == {"A", "C"}


class TestStatePersistsAcrossCycles:
    def test_hold_cycles_increment_for_surviving_symbols(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=1, hold_thresh=0)
        apply_turnover_gate(["A"], state, cfg)
        apply_turnover_gate(["A"], state, cfg)
        apply_turnover_gate(["A"], state, cfg)
        assert state.hold_cycles["A"] == 3

    def test_newly_admitted_symbol_starts_at_one(self) -> None:
        state = TurnoverState()
        cfg = TurnoverConfig(top_n=1, hold_thresh=0)
        apply_turnover_gate(["A"], state, cfg)
        apply_turnover_gate(["B"], state, cfg)
        assert state.hold_cycles.get("B") == 1
        assert "A" not in state.hold_cycles
