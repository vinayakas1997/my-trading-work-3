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


class TestSymbolGroundingCheck:
    """#6: a symbol with no basis anywhere in this turn's actual request/tool
    results is held for confirmation rather than traded on blind trust or
    silently allowed -- but only a PAUSE, never a flat reject, since a
    company name resolved to a ticker ("buy some Apple shares") legitimately
    never spells out "AAPL" anywhere, and a missing literal match must not
    be treated as proof of a mistake."""

    def test_ungrounded_symbol_is_held_for_confirmation(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        tool = _tool()
        tool._grounding_context = "the user asked about MSFT and TSLA today"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(tool.execute(symbol="AAPL", qty=10, side="buy"))

        assert result["status"] == "pending_confirmation"
        assert result["reason_code"] == "symbol_not_grounded"
        guard.check.assert_not_called()
        broker.submit_order.assert_not_called()

    def test_grounded_symbol_proceeds_normally(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        tool = _tool()
        tool._grounding_context = "the user asked to buy some AAPL shares"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(tool.execute(symbol="AAPL", qty=10, side="buy"))

        assert result["status"] == "submitted"

    def test_reduce_only_bypasses_the_grounding_check(self) -> None:
        """An exit resolved by name ("close my position") is exactly the
        case a strict grounding check would false-positive on -- and a
        risk-reducing order must never be the one held up by ambiguity,
        same posture as every other check in this file that exempts
        reduce_only."""
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        tool = _tool()
        tool._grounding_context = "close my losing position"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(tool.execute(symbol="AAPL", qty=10, side="sell", reduce_only=True))

        assert result["status"] == "submitted"

    def test_empty_grounding_context_means_no_check_at_all(self) -> None:
        """Default '' (not wired -- an older/direct caller, a test, replay
        mode) must mean 'no check', not 'reject everything'."""
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        tool = _tool()
        assert tool._grounding_context == ""

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(tool.execute(symbol="AAPL", qty=10, side="buy"))

        assert result["status"] == "submitted"

    def test_grounding_check_is_case_insensitive(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        tool = _tool()
        tool._grounding_context = "the user asked to buy some aapl shares"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(tool.execute(symbol="AAPL", qty=10, side="buy"))

        assert result["status"] == "submitted"

    def test_symbol_as_substring_of_an_unrelated_word_is_not_grounded(self) -> None:
        """situation-test/17-symbol-grounding-substring-false-negative.md: a
        plain substring test wrongly treated ticker CAT as grounded whenever
        the turn merely contained the word "Caterpillar" -- the ticker
        itself was never mentioned. Word-boundary matching must still pause
        this, the exact case #6 exists to catch."""
        broker = _configured_broker()
        guard = MagicMock()
        tool = _tool()
        tool._grounding_context = "what's the outlook for caterpillar's heavy machinery division"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(tool.execute(symbol="CAT", qty=10, side="buy"))

        assert result["status"] == "pending_confirmation"
        assert result["reason_code"] == "symbol_not_grounded"
        guard.check.assert_not_called()
        broker.submit_order.assert_not_called()

    def test_symbol_as_a_real_standalone_word_is_still_grounded(self) -> None:
        """The word-boundary fix must not become stricter than the original
        substring check for the common, legitimate case -- the ticker
        appearing as its own word (not just inside a longer word)."""
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        tool = _tool()
        tool._grounding_context = "please buy some CAT shares, I like the setup"

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(tool.execute(symbol="CAT", qty=10, side="buy"))

        assert result["status"] == "submitted"


class TestInvalidQtyRejectedBeforeGuard:
    """A negative/zero/non-finite qty must never reach OrderGuard: `value`
    (qty * price) goes negative, and reduce_only orders skip the guard's
    "cannot determine order value" fail-closed check entirely -- so a
    hallucinated negative qty + reduce_only=True would otherwise clear
    every notional/position cap outright. Rejected in the tool, before any
    guard/broker call."""

    def test_negative_qty_rejected(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(_tool().execute(symbol="AAPL", qty=-10, side="sell", reduce_only=True))

        assert result["status"] == "rejected"
        assert result["reason_code"] == "invalid_qty"
        guard.check.assert_not_called()
        broker.submit_order.assert_not_called()

    def test_zero_qty_rejected(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(_tool().execute(symbol="AAPL", qty=0, side="buy"))

        assert result["status"] == "rejected"
        assert result["reason_code"] == "invalid_qty"
        broker.submit_order.assert_not_called()

    def test_nan_qty_rejected(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(_tool().execute(symbol="AAPL", qty=float("nan"), side="buy"))

        assert result["status"] == "rejected"
        assert result["reason_code"] == "invalid_qty"
        broker.submit_order.assert_not_called()

    def test_infinite_qty_rejected(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard):
            result = json.loads(_tool().execute(symbol="AAPL", qty=float("inf"), side="buy"))

        assert result["status"] == "rejected"
        assert result["reason_code"] == "invalid_qty"
        broker.submit_order.assert_not_called()

    def test_positive_qty_still_proceeds_to_guard(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool().execute(symbol="AAPL", qty=10, side="buy"))

        assert result["status"] == "submitted"


class TestClientOrderIdIsLlmVisible:
    """client_order_id was always threaded through to broker.submit_order()
    for idempotency, but was missing from the LLM-facing tool schema -- so
    the LLM itself had no way to supply one on a retry after a timeout/
    unclear result, meaning a reasonable retry could create a real duplicate
    order. Now exposed as an optional schema property; omitting it keeps the
    exact prior behavior."""

    def test_schema_exposes_client_order_id(self) -> None:
        assert "client_order_id" in TradeTool.parameters["properties"]
        assert "client_order_id" not in TradeTool.parameters.get("required", [])

    def test_llm_supplied_client_order_id_reaches_the_broker(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool().execute(symbol="AAPL", qty=1, side="buy", client_order_id="retry-aapl-buy-1")

        assert broker.submit_order.call_args.kwargs["client_order_id"] == "retry-aapl-buy-1"

    def test_omitted_client_order_id_still_works(self) -> None:
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
        assert broker.submit_order.call_args.kwargs["client_order_id"] is None


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


class TestRejectedPayloadCarriesOrderIdentity:
    """Rejected payloads must echo symbol/side/qty like the submitted path
    does -- otherwise the post-hoc FactAuditor flags any "N shares"
    summary of a rejected order as Fail (false-positive
    AUDIT_VERDICT_FAIL noise)."""

    def _rejected(self, **kwargs) -> dict:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(False, "Trading is halted by kill switch")
        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            return json.loads(_tool().execute(symbol="AAPL", qty=10, side="buy", **kwargs))

    def test_guard_reject_echoes_symbol_side_qty(self) -> None:
        result = self._rejected()
        assert result["status"] == "rejected"
        assert result["symbol"] == "AAPL"
        assert result["side"] == "buy"
        assert result["qty"] == 10

    def test_shares_claim_after_reject_verifies(self) -> None:
        from vinu_agent.audit.fact_audit import FactAuditor

        result = self._rejected()
        history = [{"role": "tool", "name": "submit_order", "content": json.dumps(result)}]
        findings = FactAuditor().audit("Order for 10 shares of AAPL was rejected.", history)
        assert findings, "expected a shares claim to be extracted"
        assert all(f["verdict"] == "Verified" for f in findings)
