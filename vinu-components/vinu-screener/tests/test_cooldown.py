from __future__ import annotations

from vinu_screener.scan.cooldown import CooldownGate


class TestEdgeGating:
    def test_first_true_reading_fires(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=100.0) is True

    def test_staying_true_does_not_refire_without_a_new_edge(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=100.0) is True
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=101.0) is False
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=102.0) is False

    def test_false_then_true_again_is_a_fresh_edge(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=100.0) is True
        assert gate.should_fire("r1", "AAPL", False, cooldown_min=0, now=101.0) is False
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=102.0) is True

    def test_false_reading_never_fires(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", False, cooldown_min=0, now=100.0) is False


class TestCooldown:
    def test_edge_within_cooldown_window_is_suppressed(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=0.0) is True
        # false->true edge again 5 minutes later, but cooldown is 10 min
        gate.should_fire("r1", "AAPL", False, cooldown_min=10, now=200.0)
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=300.0) is False  # 5 min later

    def test_edge_after_cooldown_elapses_fires(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=0.0) is True
        gate.should_fire("r1", "AAPL", False, cooldown_min=10, now=601.0)
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=602.0) is True  # >10 min later

    def test_zero_cooldown_allows_every_edge(self) -> None:
        gate = CooldownGate()
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=0.0) is True
        gate.should_fire("r1", "AAPL", False, cooldown_min=0, now=0.1)
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=0.2) is True


class TestIsolation:
    def test_different_symbols_do_not_share_state(self) -> None:
        gate = CooldownGate()
        gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=0.0)
        assert gate.should_fire("r1", "MSFT", True, cooldown_min=0, now=0.0) is True

    def test_different_rules_do_not_share_state(self) -> None:
        gate = CooldownGate()
        gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=0.0)
        assert gate.should_fire("r2", "AAPL", True, cooldown_min=0, now=0.0) is True

    def test_reset_one_symbol(self) -> None:
        gate = CooldownGate()
        gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=0.0)
        gate.reset("r1", "AAPL")
        assert gate.state_of("r1", "AAPL") is None
        assert gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=1.0) is True

    def test_reset_whole_rule(self) -> None:
        gate = CooldownGate()
        gate.should_fire("r1", "AAPL", True, cooldown_min=10, now=0.0)
        gate.should_fire("r1", "MSFT", True, cooldown_min=10, now=0.0)
        gate.reset("r1")
        assert gate.state_of("r1", "AAPL") is None
        assert gate.state_of("r1", "MSFT") is None

    def test_state_of_reports_current_tracking(self) -> None:
        gate = CooldownGate()
        gate.should_fire("r1", "AAPL", True, cooldown_min=0, now=42.0)
        st = gate.state_of("r1", "AAPL")
        assert st is not None
        assert st.prev_condition is True
        assert st.last_fired_at == 42.0
