"""Tests for the enhanced trading playbook features in TradePlanTool."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from vinu_agent.tools.trade_plan_tool import TradePlanTool


class TestTrendBias:
    def test_extract_trend_bias_bullish(self) -> None:
        tool = TradePlanTool()
        angles = {
            "trend_lifecycle": [
                {"stage": "advancing", "direction": "up", "strength": 0.8},
            ],
        }
        assert tool._extract_trend_bias(angles) == "bullish"

    def test_extract_trend_bias_bearish_from_stage(self) -> None:
        tool = TradePlanTool()
        angles = {
            "trend_lifecycle": [
                {"stage": "declining", "direction": "down", "strength": -0.6},
            ],
        }
        assert tool._extract_trend_bias(angles) == "bearish"

    def test_extract_trend_bias_bearish_from_direction(self) -> None:
        tool = TradePlanTool()
        angles = {
            "trend_lifecycle": [
                {"stage": "mature", "direction": "down", "strength": -0.3},
            ],
        }
        assert tool._extract_trend_bias(angles) == "bearish"

    def test_extract_trend_bias_neutral(self) -> None:
        tool = TradePlanTool()
        angles = {
            "trend_lifecycle": [
                {"stage": "ranging", "direction": "flat", "strength": 0.0},
            ],
        }
        assert tool._extract_trend_bias(angles) == "neutral"

    def test_extract_trend_bias_no_data(self) -> None:
        tool = TradePlanTool()
        assert tool._extract_trend_bias({}) == "neutral"


class TestRegimeContext:
    def test_renders_regime_data(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        angles = {
            "regime_analysis": [
                {"regime": "bull_market", "volatility": "low", "avg_correlation": 0.3},
            ],
        }
        tool._render_regime_context(lines, angles)
        output = "\n".join(lines)
        assert "bull_market" in output
        assert "low" in output
        assert "0.3" in output

    def test_renders_fallback_when_empty(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_regime_context(lines, {})
        output = "\n".join(lines)
        assert "not available" in output

    def test_renders_extra_regime_fields(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        angles = {
            "regime_analysis": [
                {"regime": "crisis", "volatility_regime": "high", "correlation": 0.8, "avg_daily_move": "2.5%"},
            ],
        }
        tool._render_regime_context(lines, angles)
        output = "\n".join(lines)
        assert "crisis" in output
        assert "2.5%" in output


class TestDrawdownByRegime:
    def test_renders_drawdown_table(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        angles = {
            "drawdown_deep_dive": [
                {"label": "2022-06", "drawdown_pct": -0.25, "duration_days": 45, "recovery_status": "recovered"},
                {"label": "2023-03", "drawdown_pct": -0.12, "duration_days": 12, "recovery_status": "recovered"},
            ],
        }
        tool._render_drawdown_by_regime(lines, angles)
        output = "\n".join(lines)
        assert "Drawdown by Regime" in output
        assert "25.00%" in output or "25%" in output
        assert "12.00%" in output or "12%" in output
        assert "45" in output

    def test_skips_when_empty(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_drawdown_by_regime(lines, {})
        assert len(lines) == 0


class TestNewsSensitivity:
    def test_renders_news_table(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        news = {
            "status": "available",
            "articles": [
                {"title": "AAPL beats earnings", "published_at": "2026-07-25T10:00:00Z", "sentiment": "positive", "source": "yahoo"},
                {"title": "New iPhone launch delayed", "published_at": "2026-07-24T14:00:00Z", "sentiment": "negative", "source": "reuters"},
            ],
        }
        tool._render_news_sensitivity(lines, news)
        output = "\n".join(lines)
        assert "News Context" in output
        assert "AAPL beats earnings" in output
        assert "positive" in output
        assert "negative" in output

    def test_skips_when_unavailable(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_news_sensitivity(lines, {"status": "unavailable"})
        assert len(lines) == 0

    def test_skips_when_none(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_news_sensitivity(lines, None)
        assert len(lines) == 0


class TestTimeOfDayGuidance:
    def test_renders_session_table(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_time_of_day_guidance(lines)
        output = "\n".join(lines)
        assert "Time-of-Day Guidance" in output
        assert "Power hour" in output
        assert "Pre-market" in output
        assert "After-hours" in output
        assert "ET" in output

    def test_session_times_are_ordered(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_time_of_day_guidance(lines)
        output = "\n".join(lines)
        pre_idx = output.index("Pre-market")
        power_idx = output.index("Power hour (open)")
        assert pre_idx < power_idx


class TestLongEntryChecklist:
    def test_has_six_conditions(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        angles = {
            "trend_lifecycle": [{"stage": "advancing", "direction": "up"}],
            "trend_session_structure": [{"start": "09:30", "end": "10:30"}],
            "drawdown_deep_dive": [{"drawdown_pct": -0.05}],
            "news_price_causality": [{"causality": "confirmed"}],
        }
        tool._render_long_entry_checklist(lines, angles, {"status": "completed"}, "strong", "bullish", {"status": "available", "normal": True})
        output = "\n".join(lines)
        assert "Long Entry Conditions" in output
        assert "| 1 |" in output
        assert "| 6 |" in output

    def test_marks_trend_pending_when_weak(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_long_entry_checklist(lines, {}, {"status": "completed"}, "weak", "bearish", {"status": "unavailable"})
        output = "\n".join(lines)
        assert "PENDING" in output


class TestShortEntryChecklist:
    def test_renders_short_entry(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        angles = {
            "trend_lifecycle": [{"stage": "declining", "direction": "down"}],
            "trend_session_structure": [{"bias": "bearish"}],
        }
        tool._render_short_entry_checklist(lines, angles, {"status": "completed"}, {"status": "available", "normal": True})
        output = "\n".join(lines)
        assert "Short Entry Conditions" in output
        assert "MET" in output or "PENDING" in output or "N/A" in output


class TestFetchNews:
    def test_returns_available_with_articles(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[
                {"title": "AAPL news", "published_at": "2026-07-25", "sentiment": "positive", "source": "test"},
            ])

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://news.test")
        result = asyncio.run(self._run_fetch_news(tool, client))
        assert result["status"] == "available"
        assert len(result["articles"]) == 1

    def test_returns_unavailable_on_404(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://news.test")
        result = asyncio.run(self._run_fetch_news(tool, client))
        assert result["status"] == "unavailable"

    def test_handles_empty_articles(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://news.test")
        result = asyncio.run(self._run_fetch_news(tool, client))
        assert result["status"] == "no_articles"

    def test_handles_connection_error(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://news.test")
        result = asyncio.run(self._run_fetch_news(tool, client))
        assert result["status"] == "error"

    @staticmethod
    async def _run_fetch_news(tool: TradePlanTool, client: httpx.AsyncClient) -> dict:
        async with client:
            return await tool._fetch_news(client, "http://news.test", "AAPL")


class TestEnhancedExitChecklist:
    def test_has_eight_conditions(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_exit_checklist(lines, {}, {"status": "available"}, {"status": "available", "articles": []})
        output = "\n".join(lines)
        assert "| 1 |" in output
        assert "| 8 |" in output

    def test_news_exit_triggers_on_negative_sentiment_string(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        news = {
            "status": "available",
            "articles": [
                {"title": "Bad news", "sentiment": "negative"},
            ],
        }
        tool._render_exit_checklist(lines, {}, {"status": "available"}, news)
        output = "\n".join(lines)
        assert "EXIT" in output

    def test_news_exit_triggers_on_negative_sentiment_numeric(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        news = {
            "status": "available",
            "articles": [
                {"title": "Bad news", "sentiment": -0.5},
            ],
        }
        tool._render_exit_checklist(lines, {}, {"status": "available"}, news)
        output = "\n".join(lines)
        assert "EXIT" in output

    def test_news_exit_shows_monitor_on_positive_news(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        news = {
            "status": "available",
            "articles": [
                {"title": "Good news", "sentiment": "positive"},
            ],
        }
        tool._render_exit_checklist(lines, {}, {"status": "available"}, news)
        output = "\n".join(lines)
        assert "MONITOR" in output


def _force_active_strategies_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_strategy_store",
        side_effect=RuntimeError("not available"),
    )


class TestFetchActiveStrategiesInProcess:
    def test_returns_real_matching_strategy(self) -> None:
        from vinu_research.models import Artifact, ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(Path(tempfile.mktemp(suffix=".db")))
        active = Artifact.create("strategy", "s1", universe=["AAPL"])
        active.status = ArtifactStatus.ACTIVE
        store.upsert_artifact(active)
        other = Artifact.create("strategy", "s2", universe=["TSLA"])
        other.status = ArtifactStatus.MONITORING
        store.upsert_artifact(other)

        tool = TradePlanTool()
        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=store):
            result = asyncio.run(self._run_fetch_strategies(tool, httpx.AsyncClient()))

        assert len(result) == 1
        assert result[0]["artifact_id"] == active.artifact_id

    @staticmethod
    async def _run_fetch_strategies(tool: TradePlanTool, client: httpx.AsyncClient) -> list:
        async with client:
            return await tool._fetch_active_strategies(client, "http://research.test", "AAPL")


class TestFetchActiveStrategies:
    def test_returns_matching_strategies(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[
                {"artifact_id": "art-1", "status": "ACTIVE", "initial_sharpe": 1.5, "type": "strategy", "universe": ["AAPL"]},
                {"artifact_id": "art-2", "status": "MONITORING", "initial_sharpe": 0.8, "type": "strategy", "universe": ["TSLA"]},
            ])

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://research.test")
        with _force_active_strategies_in_process_unavailable():
            result = asyncio.run(self._run_fetch_strategies(tool, client))
        assert len(result) == 1
        assert result[0]["artifact_id"] == "art-1"

    def test_returns_empty_on_404(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://research.test")
        with _force_active_strategies_in_process_unavailable():
            result = asyncio.run(self._run_fetch_strategies(tool, client))
        assert result == []

    @staticmethod
    async def _run_fetch_strategies(tool: TradePlanTool, client: httpx.AsyncClient) -> list:
        async with client:
            return await tool._fetch_active_strategies(client, "http://research.test", "AAPL")


class TestRenderActiveStrategies:
    def test_renders_strategy_table(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        strategies = [
            {"artifact_id": "abc123def456", "status": "ACTIVE", "initial_sharpe": 1.5, "type": "strategy"},
        ]
        tool._render_active_strategies(lines, strategies)
        output = "\n".join(lines)
        assert "Active Strategies" in output
        assert "ACTIVE" in output

    def test_skips_when_empty(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_active_strategies(lines, [])
        assert len(lines) == 0


class TestTranches:
    def test_renders_with_bias(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_tranches(lines, [(1.5, 0.5), (2.5, 0.3)], "strong", "bullish")
        output = "\n".join(lines)
        assert "LONG" in output
        assert "Trend Strength" in output
        assert "Bias" in output
        assert "1.5" in output

    def test_renders_short_direction(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_tranches(lines, [(1.0, 1.0)], "weak", "bearish")
        output = "\n".join(lines)
        assert "SHORT" in output

    def test_includes_trailing_stop(self) -> None:
        tool = TradePlanTool()
        lines: list[str] = []
        tool._render_tranches(lines, [(1.0, 0.5)], "moderate", "neutral")
        output = "\n".join(lines)
        assert "Trailing stop" in output or "Trail" in output
