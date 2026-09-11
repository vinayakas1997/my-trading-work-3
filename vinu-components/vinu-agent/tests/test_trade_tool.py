"""Tests for TradeTool (submit_order) -- specifically the check-then-act
race-window fix (kill-switch race, `New-talk-agents/new-thinking/
new-restructure/phases/phase-3-kill-switch/04-implement-test.md`'s
follow-up). Two real issues fixed together: (1) `guard.pre_approve()`'s
result was silently discarded -- a halt engaged between the first
`guard.check()` and this point would correctly report not-allowed here,
but the order was submitted anyway; (2) the check-then-submit gap is now
inside `kill_switch.py`'s real OS-level `kill_switch_lock()`, the same
lock `halt_trading()` acquires, so the two can never interleave.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.broker.order_guard import GuardResult
from vinu_agent.tools.trade_tool import TradeTool


def _tool() -> TradeTool:
    tool = TradeTool()
    tool._as_of = None
    tool._session_id = ""
    return tool


def _configured_broker(submit_result=None) -> MagicMock:
    broker = MagicMock()
    broker.is_configured.return_value = True
    broker.submit_order.return_value = submit_result or {"id": "order1", "status": "accepted"}
    return broker


class TestTradeToolPreApproveResultChecked:
    def test_successful_order_submission(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=1, side="buy"))

        assert result["status"] == "submitted"
        broker.submit_order.assert_called_once()

    def test_rejected_at_initial_check_never_reaches_broker(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(False, "Trading is halted by kill switch")

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=1, side="buy"))

        assert result["status"] == "rejected"
        broker.submit_order.assert_not_called()

    def test_rejected_at_pre_approve_even_though_initial_check_passed(self) -> None:
        """The real bug: a kill switch engaged between guard.check() (the
        first gate) and guard.pre_approve() (the fresh re-check right
        before the real order) must actually stop the order -- before this
        fix, pre_approve()'s GuardResult was computed and then thrown away."""
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(False, "Trading is halted by kill switch")

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=1, side="buy"))

        assert result["status"] == "rejected"
        assert result["reason"] == "Trading is halted by kill switch"
        broker.submit_order.assert_not_called()

    def test_soft_limit_scales_the_order_down_instead_of_rejecting(self) -> None:
        # Stage C (C8): with VINU_AGENT_GUARD_SOFT_LIMITS on, a 100-share order
        # that a soft limit would only allow at 40% is submitted as 40 shares.
        from vinu_agent.broker.order_guard import MultiplierResult

        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        guard.position_size_multiplier.return_value = MultiplierResult(
            0.4, {"max_order_value": 0.4}, "max_order_value",
        )

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.broker.order_guard.SOFT_LIMITS_ENABLED", True), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=100, side="buy", limit_price=100.0))

        assert result["status"] == "submitted"
        assert result["qty"] == 40
        assert result["size_scaled"]["from_qty"] == 100
        assert result["size_scaled"]["to_qty"] == 40
        assert result["size_scaled"]["binding"] == "max_order_value"
        # the order that reached check()/submit was the scaled one
        assert guard.check.call_args.args[2] == 40

    def test_soft_limit_that_scales_below_one_share_is_rejected(self) -> None:
        from vinu_agent.broker.order_guard import MultiplierResult

        broker = _configured_broker()
        guard = MagicMock()
        guard.position_size_multiplier.return_value = MultiplierResult(
            0.004, {"risk_budget": 0.004}, "risk_budget",
        )

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.broker.order_guard.SOFT_LIMITS_ENABLED", True), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=100, side="buy", limit_price=100.0))

        assert result["status"] == "rejected"
        assert "multiplier" in result["reason"]
        broker.submit_order.assert_not_called()

    def test_soft_limits_off_by_default_leaves_qty_untouched(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=100, side="buy", limit_price=100.0))

        assert result["qty"] == 100
        assert result["size_scaled"] is None
        guard.position_size_multiplier.assert_not_called()

    def test_pre_approve_and_submit_order_both_run_inside_the_kill_switch_lock(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        events: list[str] = []
        guard.pre_approve.side_effect = lambda *a, **kw: (events.append("pre_approve"), GuardResult(True))[1]
        broker.submit_order.side_effect = lambda **kw: (events.append("submit_order"), {"id": "o1", "status": "accepted"})[1]

        class _RecordingLock:
            def __enter__(self):
                events.append("lock_acquired")
                return self

            def __exit__(self, *a):
                events.append("lock_released")
                return False

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.broker.kill_switch.kill_switch_lock", return_value=_RecordingLock()), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool().execute(symbol="AAPL", qty=1, side="buy")

        assert events == ["lock_acquired", "pre_approve", "submit_order", "lock_released"]
