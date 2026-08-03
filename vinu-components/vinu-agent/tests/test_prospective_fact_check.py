"""Tests for Piece 3 — prospective fact-check.

Named acceptance test (implementation-plan-from-04/AGENTS.md): reconstruct
the actual JNJ replay scenario — a plan about to state a price with no
matching tool call this session — and confirm it's caught BEFORE the plan
is committed (journaled), not only after a final answer is composed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _tool() -> TradePlanTool:
    tool = TradePlanTool()
    tool._session_id = "s1"
    return tool


class TestProspectiveFactCheck:
    def test_price_backed_by_fetched_data_passes(self) -> None:
        tool = _tool()
        angles = {"regime_analysis": [{"sharpe": 1.2}]}
        features = {"data": [{"close": 267.16}]}
        findings = tool._prospective_fact_check(
            "JNJ is trading at $267.16 today.",
            angles=angles, features=features, validation={}, liquidity={}, news={},
        )
        assert all(f["verdict"] != "Fail" for f in findings)

    def test_jnj_style_fabricated_price_is_caught(self) -> None:
        """The actual replay bug: JNJ stated at $162.45 with no tool call
        this session backing it (real value was ~$267.16)."""
        tool = _tool()
        angles = {"regime_analysis": [{"sharpe": 1.2}]}
        features = {"data": [{"close": 267.16}]}
        findings = tool._prospective_fact_check(
            "JNJ is trading at $162.45 today, a strong entry point.",
            angles=angles, features=features, validation={}, liquidity={}, news={},
        )
        assert any(f["verdict"] == "Fail" and f["claimed_value"] == 162.45 for f in findings)

    def test_no_symbol_tied_numbers_produces_no_findings(self) -> None:
        tool = _tool()
        findings = tool._prospective_fact_check(
            "No numeric claims here at all.",
            angles={}, features={}, validation={}, liquidity={}, news={},
        )
        assert findings == []


class TestRenderFactCheckWarning:
    def test_warning_lists_each_blocking_claim(self) -> None:
        blocking = [
            {"symbol": "JNJ", "claim_type": "price", "claimed_value": 162.45, "raw_match": "$162.45", "verdict": "Fail"},
        ]
        warning = TradePlanTool._render_fact_check_warning(blocking)
        assert "NOT journaled" in warning
        assert "JNJ" in warning
        assert "162.45" in warning


def _wire_execute_async_stubs(tool: TradePlanTool) -> None:
    """Stub every fetch/render helper _execute_async calls so the test
    exercises only the real gating logic (prospective check -> journal or
    not), not the network layer."""
    tool._symbol_has_analysis = AsyncMock(return_value=True)
    tool._fetch_angles = AsyncMock(return_value={})
    tool._fetch_features = AsyncMock(return_value={})
    tool._fetch_validation = AsyncMock(return_value={})
    tool._fetch_liquidity_check = AsyncMock(return_value={})
    tool._fetch_news = AsyncMock(return_value={})
    tool._fetch_active_strategies = AsyncMock(return_value={})
    tool._fetch_frozen_trade_plan = AsyncMock(return_value={"status": "unavailable"})
    tool._extract_trend_stage = MagicMock(return_value="moderate")
    tool._extract_trend_bias = MagicMock(return_value="neutral")
    tool._build_structured_plan = MagicMock(return_value={"symbol": "JNJ"})
    tool._render_plan = MagicMock(return_value="rendered markdown")
    tool._render_plan_json_block = MagicMock(return_value="{}")


class TestJournalWriteGating:
    """Confirms the real _execute_async control flow: a Fail-verdict finding
    from _prospective_fact_check must skip _schedule_journal_write and
    prepend the warning block; a clean result must still journal."""

    def test_blocked_plan_skips_journal_write_and_prepends_warning(self) -> None:
        tool = _tool()
        _wire_execute_async_stubs(tool)
        blocking_finding = {
            "symbol": "JNJ", "claim_type": "price", "claimed_value": 162.45,
            "raw_match": "$162.45", "verdict": "Fail",
        }
        with patch.object(tool, "_prospective_fact_check", return_value=[blocking_finding]), \
             patch.object(tool, "_schedule_journal_write") as mock_schedule, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = AsyncMock()
            output = asyncio.run(tool._execute_async(symbol="JNJ"))

        mock_schedule.assert_not_called()
        assert "NOT journaled" in output
        assert "JNJ" in output

    def test_clean_plan_calls_journal_write(self) -> None:
        tool = _tool()
        _wire_execute_async_stubs(tool)
        with patch.object(tool, "_prospective_fact_check", return_value=[]), \
             patch.object(tool, "_schedule_journal_write") as mock_schedule, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = AsyncMock()
            output = asyncio.run(tool._execute_async(symbol="JNJ"))

        mock_schedule.assert_called_once()
        assert "NOT journaled" not in output
