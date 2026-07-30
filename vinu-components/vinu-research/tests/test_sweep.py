from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vinu_research.models import BacktestMetrics, BacktestResult
from vinu_research.sweep import (
    ParameterNotFoundError,
    build_candidate_code,
    run_sweep_candidate,
    substitute_param_value,
)

SIMPLE_CODE = """
class UserStrategy:
    def __init__(self, config=None):
        self.fast_period = 20
        self.slow_period = 50

    def compute_signals(self, data):
        return data['close'].rolling(self.fast_period).mean()
"""


class TestSubstituteParamValue:
    def test_replaces_matching_self_attribute_assignment(self) -> None:
        result = substitute_param_value(SIMPLE_CODE, "fast_period", 9)
        assert "self.fast_period = 9" in result
        assert "self.slow_period = 50" in result

    def test_replaces_all_occurrences_of_same_name(self) -> None:
        code = "x = 5\ny = x\nx = 5\n"
        result = substitute_param_value(code, "x", 99)
        assert result.count("x = 99") == 2

    def test_raises_when_param_not_found(self) -> None:
        with pytest.raises(ParameterNotFoundError):
            substitute_param_value(SIMPLE_CODE, "nonexistent_param", 5)

    def test_does_not_touch_string_or_comment_matches(self) -> None:
        code = "# fast_period is mentioned here\nlabel = 'fast_period'\nfast_period = 20\n"
        result = substitute_param_value(code, "fast_period", 7)
        assert "label = 'fast_period'" in result
        assert "fast_period = 7" in result

    def test_only_substitutes_numeric_constants(self) -> None:
        code = "fast_period = 'not_a_number'\n"
        with pytest.raises(ParameterNotFoundError):
            substitute_param_value(code, "fast_period", 7)


class TestBuildCandidateCode:
    def test_recipe_mode_generates_code(self) -> None:
        code, params_used = build_candidate_code(recipe="crossover", params={"fast_period": 9, "slow_period": 40})
        assert "class UserStrategy" in code
        assert params_used == {"fast_period": 9, "slow_period": 40}

    def test_base_code_mode_substitutes(self) -> None:
        code, params_used = build_candidate_code(base_code=SIMPLE_CODE, param_name="fast_period", param_value=5)
        assert "self.fast_period = 5" in code
        assert params_used == {"fast_period": 5}

    def test_unknown_recipe_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown recipe"):
            build_candidate_code(recipe="not_a_real_recipe", params={})

    def test_rejects_both_modes_specified(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            build_candidate_code(recipe="crossover", params={}, base_code=SIMPLE_CODE, param_name="x", param_value=1)

    def test_rejects_neither_mode_specified(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            build_candidate_code()

    def test_base_code_mode_requires_param_name_and_value(self) -> None:
        with pytest.raises(ValueError, match="requires both"):
            build_candidate_code(base_code=SIMPLE_CODE)


class TestRunSweepCandidate:
    @pytest.mark.asyncio
    async def test_calls_run_backtest_and_extracts_validation(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.return_value = BacktestResult(
            run_id="abc123",
            strategy_name="UserStrategy",
            metrics=BacktestMetrics(sharpe_ratio=1.5),
            benchmark_metrics={},
            trade_count=42,
            equity_points=100,
            raw={"validation": {"passed": True, "reasons": []}},
        )

        result = await run_sweep_candidate(
            symbol="AAPL",
            from_date="2023-01-01",
            to_date="2023-12-31",
            recipe="crossover",
            params={"fast_period": 9, "slow_period": 40},
            tools=mock_tools,
        )

        assert result.run_id == "abc123"
        assert result.validation == {"passed": True, "reasons": []}
        assert result.trade_count == 42
        assert result.params_used == {"fast_period": 9, "slow_period": 40}
        mock_tools.run_backtest.assert_awaited_once()
        _, kwargs = mock_tools.run_backtest.call_args
        assert kwargs["run_validation"] is True
        assert kwargs["symbols"] == ["AAPL"]

    @pytest.mark.asyncio
    async def test_raises_when_backtest_returns_none(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.return_value = None

        with pytest.raises(RuntimeError, match="no result"):
            await run_sweep_candidate(
                symbol="AAPL",
                from_date="2023-01-01",
                to_date="2023-12-31",
                recipe="crossover",
                params={"fast_period": 9, "slow_period": 40},
                tools=mock_tools,
            )
