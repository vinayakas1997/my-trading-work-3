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


class TestAuditLoggerReadAll:
    """Analysis O (25-A-Y-details/05-governance-freshness.md) needs a bulk
    read, unlike `search()`'s ref-id substring match."""

    def test_returns_every_entry_in_written_order(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        log_path = tmp_path / "trade_audit.log"
        with patch.object(AuditLogger, "LOG_PATH", log_path):
            AuditLogger.log("order_placed", {"seq": 0}, symbol="AAPL")
            AuditLogger.log("order_rejected", {"seq": 1}, symbol="MSFT")
            entries = AuditLogger.read_all()

        assert [e["details"]["seq"] for e in entries] == [0, 1]

    def test_filters_by_action(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        log_path = tmp_path / "trade_audit.log"
        with patch.object(AuditLogger, "LOG_PATH", log_path):
            AuditLogger.log("order_placed", {}, symbol="AAPL")
            AuditLogger.log("order_rejected", {"reason": "x"}, symbol="MSFT")
            AuditLogger.log("order_rejected", {"reason": "y"}, symbol="AAPL")
            entries = AuditLogger.read_all(action="order_rejected")

        assert len(entries) == 2
        assert all(e["action"] == "order_rejected" for e in entries)

    def test_missing_log_file_returns_empty_list_not_error(self, tmp_path) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        with patch.object(AuditLogger, "LOG_PATH", tmp_path / "never_written.log"):
            assert AuditLogger.read_all() == []

    def test_log_path_override_reads_a_different_file_than_the_class_default(self, tmp_path) -> None:
        """The override a reader in a different process/service needs --
        same convention as `vinu_infra.trade_audit_log.read_all(log_path=...)`."""
        from vinu_agent.broker.kill_switch import AuditLogger

        real_log = tmp_path / "real.log"
        other_log = tmp_path / "other.log"
        with patch.object(AuditLogger, "LOG_PATH", real_log):
            AuditLogger.log("order_rejected", {"which": "real"})
        with patch.object(AuditLogger, "LOG_PATH", other_log):
            AuditLogger.log("order_rejected", {"which": "other"})

        entries = AuditLogger.read_all(log_path=other_log)
        assert len(entries) == 1
        assert entries[0]["details"]["which"] == "other"


class TestStrategyEvaluationWrite:
    """missing-pieces-of-system/startegy-enhancer/01-plan.md section 2,
    order_guard (step_order=10) -- the structurally-unbypassable one."""

    def test_passed_order_writes_pass(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool("sess-42").execute(symbol="AAPL", qty=1, side="buy")

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        eval_store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        rows = eval_store.list_status_for_ticker("AAPL")
        assert any(r["artifact_id"] == "order:AAPL" for r in rows)

    def test_passed_order_resolves_the_real_active_artifact_id(self, tmp_path, monkeypatch) -> None:
        """Real fix, 2026-09-21: this used to always be the synthetic
        f"order:{symbol}" id. Confirms it now resolves the actual ACTIVE
        artifact for the symbol via the same in-process store
        OrderGuard._check_active_artifact() already reads."""
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        research_root = tmp_path / "research"
        research_root.mkdir()
        monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))

        from vinu_research.models import Artifact, ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(research_root / "strategy_store.db")
        artifact = Artifact.create("strategy", "AAPL-real", universe=["AAPL"])
        artifact.status = ArtifactStatus.ACTIVE
        store.upsert_artifact(artifact)

        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool("sess-42").execute(symbol="AAPL", qty=1, side="buy")

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        eval_store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        rows = eval_store.list_status_for_ticker("AAPL")
        assert any(r["artifact_id"] == artifact.artifact_id for r in rows)
        assert not any(r["artifact_id"] == "order:AAPL" for r in rows)

    def test_rejected_order_writes_fail_with_real_reason(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(False, reason="daily order cap reached")

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            _tool("sess-42").execute(symbol="AAPL", qty=1, side="buy")

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        eval_store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        history = eval_store.get_history("order:AAPL")
        og_rows = [h for h in history if h["step_name"] == "order_guard"]
        assert len(og_rows) == 1
        assert og_rows[0]["verdict"] == "FAIL"
        assert og_rows[0]["reasoning"] == "daily order cap reached"

    def test_unset_env_ships_inert(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
        broker = _configured_broker()
        guard = MagicMock()
        guard.check.return_value = GuardResult(True)
        guard.pre_approve.return_value = GuardResult(True)

        with patch("vinu_agent.tools.trade_tool.get_live_broker", return_value=broker), \
             patch("vinu_agent.tools.trade_tool.OrderGuard", return_value=guard), \
             patch("vinu_agent.tools.trade_tool.TradingMandate") as MockMandate:
            MockMandate.load.return_value = MagicMock(require_confirmation=False, to_dict=lambda: {})
            # Must not raise when the shared data root isn't configured.
            result = json.loads(_tool("sess-42").execute(symbol="AAPL", qty=1, side="buy"))
        assert result["status"] == "submitted"
