"""Phase 2 fix: trade_plan_tool.py's own locally-computed entry_rules/
exit_rules (from _build_structured_plan) used to be dropped on the floor --
never merged into the frozen research TradePlan's entry_checklist/
exit_checklist, even though both are the same {"condition", ...} shape.
_author_and_freeze_trade_plan_in_process now forwards them through
author_trade_plan's extra_checklist_entries kwarg so they actually reach the
frozen plan."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from vinu_agent.tools.trade_plan_tool import TradePlanTool


class TestAuthorAndFreezeMergesChecklistEntries:
    def test_extra_checklist_entries_forwarded_to_author_trade_plan(self) -> None:
        tool = TradePlanTool()
        extra = {
            "entry_rules": [{"condition": "adequate_liquidity", "status": "met", "source": "stock-price"}],
            "exit_rules": [{"condition": "trend_reversal", "action": "exit", "source": "trend_lifecycle"}],
        }

        fake_plan = MagicMock()
        fake_tools = MagicMock()
        fake_tools.close = AsyncMock()
        author_mock = AsyncMock(return_value=fake_plan)
        freeze_mock = MagicMock(return_value=MagicMock(artifact_id="art_1", trade_plan_data="{}"))

        with patch("vinu_research.trade_plan_authoring.author_trade_plan", author_mock), \
             patch("vinu_research.trade_plan_authoring.freeze_trade_plan", freeze_mock), \
             patch("vinu_agent.broker.research_link.get_research_config", return_value=MagicMock()), \
             patch("vinu_agent.broker.research_link.get_research_tools", return_value=fake_tools), \
             patch("vinu_agent.broker.research_link.get_strategy_store", return_value=MagicMock()), \
             patch("vinu_agent.broker.research_link.serialize_trade_plan_artifact", return_value={"artifact_id": "art_1"}):
            asyncio.run(tool._author_and_freeze_trade_plan_in_process(
                "AAPL", "daily", summary_context=None, extra_checklist_entries=extra,
            ))

        assert author_mock.await_args.kwargs["extra_checklist_entries"] == extra

    def test_none_extra_checklist_entries_is_forwarded_unchanged(self) -> None:
        tool = TradePlanTool()
        fake_plan = MagicMock()
        fake_tools = MagicMock()
        fake_tools.close = AsyncMock()
        author_mock = AsyncMock(return_value=fake_plan)
        freeze_mock = MagicMock(return_value=MagicMock(artifact_id="art_1", trade_plan_data="{}"))

        with patch("vinu_research.trade_plan_authoring.author_trade_plan", author_mock), \
             patch("vinu_research.trade_plan_authoring.freeze_trade_plan", freeze_mock), \
             patch("vinu_agent.broker.research_link.get_research_config", return_value=MagicMock()), \
             patch("vinu_agent.broker.research_link.get_research_tools", return_value=fake_tools), \
             patch("vinu_agent.broker.research_link.get_strategy_store", return_value=MagicMock()), \
             patch("vinu_agent.broker.research_link.serialize_trade_plan_artifact", return_value={"artifact_id": "art_1"}):
            asyncio.run(tool._author_and_freeze_trade_plan_in_process("AAPL", "daily"))

        assert author_mock.await_args.kwargs["extra_checklist_entries"] is None
