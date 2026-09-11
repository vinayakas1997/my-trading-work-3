"""Traceability fix (2026-09-11): every AuditLogger.log() call TradeTool
makes now carries `session_id`, and a new `order_placed` entry captures the
broker's real order id -- previously neither was true, so an audit entry
could never be traced back to the session that caused it, and a
successfully submitted order's real id was never written to the audit
trail at all. See broker/kill_switch.py's `AuditLogger.search()`.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.broker.order_guard import GuardResult
from vinu_agent.tools.trade_tool import TradeTool


def _tool(session_id: str = "sess-42") -> TradeTool:
    tool = TradeTool()
    tool._as_of = None
    tool._session_id = session_id
    return tool


def _configured_broker(submit_result=None) -> MagicMock:
    broker = MagicMock()
    broker.is_configured.return_value = True
    broker.submit_order.return_value = submit_result or {"id": "order-real-1", "status": "accepted"}
    return broker


class TestSessionIdIsCarriedOnEveryAuditEntry:
    def test_successful_submission_logs_order_placed_with_session_and_order_id(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate, \
             patch("vinu_agent.tools.trade_tool.AuditLogger") as MockAudit:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool("sess-42").execute(symbol="AAPL", qty=1, side="buy"))

        assert result["status"] == "submitted"
        placed_calls = [c for c in MockAudit.log.call_args_list if c.args[0] == "order_placed"]
        assert len(placed_calls) == 1
        args, kwargs = placed_calls[0]
        assert args[1]["order_id"] == "order-real-1"
        assert kwargs["session_id"] == "sess-42"
        assert kwargs["symbol"] == "AAPL"
        # Every call this run made (executing + placed) carries the session id.
        for call in MockAudit.log.call_args_list:
            assert call.kwargs.get("session_id") == "sess-42"

    def test_rejection_at_initial_check_still_carries_session_id(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(False, "Trading is halted by kill switch")

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate, \
             patch("vinu_agent.tools.trade_tool.AuditLogger") as MockAudit:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool("sess-99").execute(symbol="AAPL", qty=1, side="buy")

        MockAudit.log.assert_called_once()
        args, kwargs = MockAudit.log.call_args
        assert args[0] == "order_rejected"
        assert kwargs["session_id"] == "sess-99"

    def test_rejection_at_pre_approve_carries_session_id(self) -> None:
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(False, "halted between check and submit")

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate, \
             patch("vinu_agent.tools.trade_tool.AuditLogger") as MockAudit:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool("sess-7").execute(symbol="AAPL", qty=1, side="buy")

        rejected_calls = [c for c in MockAudit.log.call_args_list if c.args[0] == "order_rejected"]
        assert len(rejected_calls) == 1
        assert rejected_calls[0].kwargs["session_id"] == "sess-7"

    def test_broker_exception_logs_order_error_with_session_id(self) -> None:
        broker = _configured_broker()
        broker.submit_order.side_effect = RuntimeError("broker down")
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate, \
             patch("vinu_agent.tools.trade_tool.AuditLogger") as MockAudit:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            result = json.loads(_tool("sess-err").execute(symbol="AAPL", qty=1, side="buy"))

        assert result["status"] == "error"
        error_calls = [c for c in MockAudit.log.call_args_list if c.args[0] == "order_error"]
        assert len(error_calls) == 1
        assert error_calls[0].kwargs["session_id"] == "sess-err"


class TestAuditLoggerSearch:
    def test_finds_entries_containing_the_ref_id_anywhere(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        log_path = tmp_path / "trade_audit.log"
        with patch.object(AuditLogger, "LOG_PATH", log_path):
            AuditLogger.log("order_placed", {"order_id": "abc123"}, session_id="sess-1", symbol="AAPL")
            AuditLogger.log("order_placed", {"order_id": "xyz789"}, session_id="sess-2", symbol="MSFT")

            by_session = AuditLogger.search("sess-1")
            by_order_id = AuditLogger.search("abc123")

        assert len(by_session) == 1
        assert by_session[0]["session_id"] == "sess-1"
        assert len(by_order_id) == 1
        assert by_order_id[0]["details"]["order_id"] == "abc123"

    def test_newest_first_and_limit_respected(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        log_path = tmp_path / "trade_audit.log"
        with patch.object(AuditLogger, "LOG_PATH", log_path):
            for i in range(5):
                AuditLogger.log("order_placed", {"seq": i}, session_id="sess-x")
            results = AuditLogger.search("sess-x", limit=2)

        assert len(results) == 2
        assert results[0]["details"]["seq"] == 4
        assert results[1]["details"]["seq"] == 3

    def test_unknown_ref_id_returns_empty_list(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        log_path = tmp_path / "trade_audit.log"
        with patch.object(AuditLogger, "LOG_PATH", log_path):
            AuditLogger.log("order_placed", {"order_id": "abc123"}, session_id="sess-1")
            assert AuditLogger.search("no-such-id") == []

    def test_missing_log_file_returns_empty_list_not_error(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        with patch.object(AuditLogger, "LOG_PATH", tmp_path / "never_written.log"):
            assert AuditLogger.search("anything") == []
