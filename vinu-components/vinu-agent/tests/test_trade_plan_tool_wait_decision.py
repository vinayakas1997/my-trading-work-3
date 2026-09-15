"""Regression for the missing WAIT-decision ledger event: every other trade
-plan outcome (rejected, funded, pendblocked) gets a TickerLedgerStore
event; a deliberate WAIT never did, even though the plan itself is still
frozen into the strategy store either way. See
_author_and_freeze_trade_plan_in_process's `_log_wait_decision` call and
the foundation-fixes audit in missing-pieces-of-system/narating-agents/.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _plan(entry_decision: str, *, tier: str = "moderate", reasons: list[str] | None = None) -> SimpleNamespace:
    trade_score = SimpleNamespace(tier=tier, reasons=reasons or []) if entry_decision == "WAIT" else None
    return SimpleNamespace(entry_decision=entry_decision, trade_score=trade_score)


def _run(tool: TradePlanTool, plan) -> dict:
    artifact = SimpleNamespace(artifact_id="art_1")
    tools = MagicMock()
    tools.close = AsyncMock()
    with patch("vinu_research.trade_plan_authoring.author_trade_plan", new=AsyncMock(return_value=plan)), \
         patch("vinu_research.trade_plan_authoring.freeze_trade_plan", return_value=artifact), \
         patch("vinu_agent.broker.research_link.get_research_config", return_value=MagicMock()), \
         patch("vinu_agent.broker.research_link.get_research_tools", return_value=tools), \
         patch("vinu_agent.broker.research_link.get_strategy_store", return_value=MagicMock()), \
         patch("vinu_agent.broker.research_link.serialize_trade_plan_artifact", return_value={"artifact_id": "art_1"}):
        return asyncio.run(tool._author_and_freeze_trade_plan_in_process("AAPL", "daily"))


class TestWaitDecisionLogging:
    def test_wait_decision_writes_ledger_event(self) -> None:
        tool = TradePlanTool()
        tool._ticker_ledger_store = MagicMock()
        plan = _plan("WAIT", tier="watch", reasons=["confluence below threshold"])

        _run(tool, plan)

        tool._ticker_ledger_store.add_event.assert_called_once()
        _, kwargs = tool._ticker_ledger_store.add_event.call_args
        assert kwargs["ticker"] == "AAPL"
        assert kwargs["stage"] == "trade_plan"
        assert kwargs["event_type"] == "wait_decision"
        assert kwargs["ref_id"] == "art_1"
        assert "confluence below threshold" in kwargs["text"]
        assert "watch" in kwargs["text"]

    def test_non_wait_decision_writes_nothing(self) -> None:
        tool = TradePlanTool()
        tool._ticker_ledger_store = MagicMock()
        plan = _plan("BUY")

        _run(tool, plan)

        tool._ticker_ledger_store.add_event.assert_not_called()

    def test_no_ledger_store_configured_does_not_raise(self) -> None:
        tool = TradePlanTool()
        assert tool._ticker_ledger_store is None
        plan = _plan("WAIT")

        result = _run(tool, plan)  # must not raise

        assert result == {"artifact_id": "art_1"}

    def test_ledger_write_failure_does_not_break_authoring(self) -> None:
        tool = TradePlanTool()
        tool._ticker_ledger_store = MagicMock()
        tool._ticker_ledger_store.add_event.side_effect = RuntimeError("db locked")
        plan = _plan("WAIT")

        result = _run(tool, plan)  # must not raise

        assert result == {"artifact_id": "art_1"}

    def test_wait_with_no_trade_score_uses_fallback_text(self) -> None:
        tool = TradePlanTool()
        tool._ticker_ledger_store = MagicMock()
        plan = SimpleNamespace(entry_decision="WAIT", trade_score=None)

        _run(tool, plan)

        _, kwargs = tool._ticker_ledger_store.add_event.call_args
        assert "WAIT" in kwargs["text"]
