"""C5 fix: the empty-meaning contract, one test per spelling. No behavior
is changed here -- each test pins what the code already does, so a future
caller (or agent tool) can tell "no rows" from "not yet run" from "real
error". The same table lives in
vinu-research/.../server/routes_introspect.py's module docstring and in
newer-thinking-with-discussed/how-system-implemented.md's appendix."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.loop import StrategyResearchLoop, _classify_outcome_status
from vinu_research.models import BacktestMetrics, BacktestResult, CriticFeedback, IterationRecord
from vinu_research.sweep_grid import run_sweep_grid
from vinu_research.sweep_store import SweepGridStore


def _history_with_infra_failure() -> list[IterationRecord]:
    return [
        IterationRecord(
            iteration=1, strategy_code="class UserStrategy: pass", result=None,
            critique=CriticFeedback(
                verdict={"passed": False, "reasons": ["infra"]},
                reasoning="INFRASTRUCTURE FAILURE: simulator unreachable",
                suggestions=[],
            ),
        )
    ]


class TestOutcomeStatusSpellings:
    def test_passed_means_a_best_result_exists(self) -> None:
        result = BacktestResult(
            run_id="r1", strategy_name="s",
            metrics=BacktestMetrics.from_dict({"sharpe_ratio": 1.0}),
            benchmark_metrics={}, trade_count=10, equity_points=10, raw={},
        )
        assert _classify_outcome_status([], result) == "passed"

    def test_no_history_no_result_is_no_strategy_found_not_infra_failure(self) -> None:
        assert _classify_outcome_status([], None) == "no_strategy_found"

    def test_infra_prefix_is_infra_failure(self) -> None:
        assert _classify_outcome_status(_history_with_infra_failure(), None) == "infra_failure"


class TestSweepEmptySpellings:
    @pytest.mark.asyncio
    async def test_all_points_failing_yields_empty_ranked_no_pbo_no_walkforward(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = RuntimeError("boom")

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover",
            param_grid=[{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 50}],
            tools=mock_tools, persist=False,
        )

        assert result.ranked == []
        assert result.succeeded == 0
        assert result.completeness == 0.0
        assert result.pbo is None
        assert result.walk_forward is None

    @pytest.mark.asyncio
    async def test_blank_sweep_id_means_not_persisted_uuid_means_persisted(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = RuntimeError("boom")

        unpersisted = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=[{"fast_period": 5, "slow_period": 40}],
            tools=mock_tools, persist=False,
        )
        assert unpersisted.sweep_id == ""

        persisted = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=[{"fast_period": 5, "slow_period": 40}],
            tools=mock_tools, persist=True, sweep_store=SweepGridStore(":memory:"),
        )
        assert persisted.sweep_id != ""


class TestGenerationStoreEmptySpelling:
    def test_none_store_is_a_deliberate_no_op_not_a_miswire(self) -> None:
        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        assert loop._generation_candidate_store is None
        # Must not raise even with a real ranked list to record.
        assert loop._record_generation_round(1, "llm", [object()]) is None


class TestAgentEvalEmptySpelling:
    def test_unset_env_is_inert_empty_string(self, monkeypatch) -> None:
        from vinu_agent.agent.scheduler_workers import _strategy_evaluation_context_for_ticker

        monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
        assert _strategy_evaluation_context_for_ticker("AAPL") == ""
