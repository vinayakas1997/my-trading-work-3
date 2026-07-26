"""Tests for the portfolio correlation gate (Phase 10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from vinu_research.config import ResearchConfig
from vinu_research.gates.correlation_gate import (
    CorrelationVerdict,
    _backtest_and_get_returns,
    check_correlation_gate,
)
from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.promotion import PromotionVerdict, meets_promotion_bar


def make_artifact(artifact_id: str = "art_test", strategy_code: str = "def generate_weights(data):\n    return 0") -> Artifact:
    return Artifact(
        artifact_id=artifact_id,
        type="strategy",
        name="test_artifact",
        universe=["AAPL"],
        status=ArtifactStatus.ACTIVE,
        strategy_code=strategy_code,
        initial_sharpe=1.5,
        deflated_sharpe=0.96,
        holdout_passed=True,
        stress_test_passed=True,
    )


class TestCheckCorrelationGate:
    @pytest.mark.asyncio
    async def test_no_active_strategies_passes(self):
        cfg = ResearchConfig()
        tools = MagicMock()
        verdict = await check_correlation_gate(
            candidate_code="code", candidate_symbol="AAPL",
            from_date="2024-01-01", to_date="2024-06-01",
            active_strategies=[], tools=tools, config=cfg,
        )
        assert verdict.eligible is True

    @pytest.mark.asyncio
    async def test_active_strategies_without_code_skipped(self):
        cfg = ResearchConfig()
        tools = AsyncMock()
        tools.run_backtest.return_value = None

        active = [make_artifact(strategy_code="")]
        verdict = await check_correlation_gate(
            candidate_code="code", candidate_symbol="AAPL",
            from_date="2024-01-01", to_date="2024-06-01",
            active_strategies=active, tools=tools, config=cfg,
        )
        assert verdict.eligible is True

    @pytest.mark.asyncio
    async def test_returns_verdict_with_correlations(self):
        cfg = ResearchConfig(promotion_correlation_threshold=0.85)

        returns_a = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.01, 0.02, -0.02, 0.01, 0.03, -0.01],
                              index=pd.date_range("2024-01-01", periods=12, freq="D"))
        returns_b = pd.Series([0.05, 0.04, 0.06, 0.03, 0.05, 0.04, 0.03, 0.05, 0.04, 0.06, 0.05, 0.04],
                              index=pd.date_range("2024-01-01", periods=12, freq="D"))

        tools = AsyncMock()
        bt_mock = MagicMock()
        bt_mock.run_id = "test_run"
        tools.run_backtest.return_value = bt_mock
        tools.fetch_equity_returns.side_effect = [returns_a, returns_b]

        active = [make_artifact(artifact_id="art_active_1")]
        verdict = await check_correlation_gate(
            candidate_code="code", candidate_symbol="AAPL",
            from_date="2024-01-01", to_date="2024-06-01",
            active_strategies=active, tools=tools, config=cfg,
        )
        assert verdict.n_active == 1
        assert len(verdict.correlations) == 1
        assert verdict.avg_correlation is not None


class TestMeetsPromotionBar:
    def test_passes_without_correlation_verdict(self):
        cfg = ResearchConfig()
        artifact = make_artifact()
        verdict = meets_promotion_bar(artifact, cfg)
        assert verdict.eligible is True

    def test_correlation_verdict_appended_to_reasons(self):
        cfg = ResearchConfig()
        artifact = make_artifact()
        cv = CorrelationVerdict(eligible=False, avg_correlation=0.95, reasons=["avg correlation 0.950 exceeds threshold 0.85"])
        verdict = meets_promotion_bar(artifact, cfg, correlation_verdict=cv)
        assert verdict.eligible is False
        assert any("correlation" in r for r in verdict.reasons)


class TestPromotionConfig:
    def test_defaults(self):
        cfg = ResearchConfig()
        assert cfg.promotion_correlation_threshold == 0.85
        assert cfg.promotion_correlation_required is False

    def test_custom_threshold(self):
        cfg = ResearchConfig(promotion_correlation_threshold=0.75, promotion_correlation_required=True)
        assert cfg.promotion_correlation_threshold == 0.75
        assert cfg.promotion_correlation_required is True


class TestBacktestAndGetReturns:
    @pytest.mark.asyncio
    async def test_returns_none_when_backtest_fails(self):
        tools = AsyncMock()
        tools.run_backtest.return_value = None
        result = await _backtest_and_get_returns(tools, "code", "AAPL", "2024-01-01", "2024-06-01", "1d")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_equity_fetch_fails(self):
        tools = AsyncMock()
        bt = MagicMock()
        bt.run_id = "test_run"
        tools.run_backtest.return_value = bt
        tools.fetch_equity_returns.return_value = None
        result = await _backtest_and_get_returns(tools, "code", "AAPL", "2024-01-01", "2024-06-01", "1d")
        assert result is None
