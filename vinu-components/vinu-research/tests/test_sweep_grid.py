from __future__ import annotations

from unittest.mock import AsyncMock

import numpy as np
import pytest

from vinu_research.models import BacktestMetrics, BacktestResult
from vinu_research.sweep_grid import GridTooLargeError, MAX_GRID_POINTS, run_sweep_grid


def _bt_result(run_id: str, sharpe: float, *, equity_points: int = 100, daily_returns=None) -> BacktestResult:
    raw = {"equity_points": equity_points, "benchmark_metrics": {}}
    if daily_returns is not None:
        raw["daily_returns"] = daily_returns
    return BacktestResult(
        run_id=run_id,
        strategy_name="UserStrategy",
        metrics=BacktestMetrics(sharpe_ratio=sharpe, total_return=0.05, max_drawdown=-0.1, win_rate=0.55),
        benchmark_metrics={},
        trade_count=42,
        equity_points=equity_points,
        raw=raw,
    )


class TestRunSweepGridRecipeMode:
    @pytest.mark.asyncio
    async def test_returns_ranked_table_in_one_call_for_a_12_point_grid(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = [
            _bt_result(f"run-{i}", sharpe=float(i)) for i in range(12)
        ]
        grid = [{"fast_period": 5 + i, "slow_period": 40} for i in range(12)]

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=grid, tools=mock_tools,
        )

        assert mock_tools.run_backtest.await_count == 12  # 12 internal calls...
        assert result.requested == 12
        assert result.succeeded == 12
        assert result.completeness == 1.0
        assert len(result.ranked) == 12
        # ...but the ranked table comes back as ONE result object -- the
        # caller (an LLM tool call) only ever sees a single round-trip.

    @pytest.mark.asyncio
    async def test_ranked_entries_carry_real_run_id_and_metrics_not_just_score(self) -> None:
        """A ranked table that only reports scores is useless to
        backtest_runner/the manager -- they need the winning candidate's
        real run_id, code, and metrics to report and to hand off to
        risk_critic. rank_candidates() alone doesn't carry this (it wraps
        LlmCandidate, not SweepCandidateResult) -- run_sweep_grid must
        reattach it after ranking."""
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = [
            _bt_result("run-low", sharpe=0.1),
            _bt_result("run-high", sharpe=5.0),
        ]
        grid = [{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}]

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=grid, tools=mock_tools,
        )

        top = result.ranked[0]
        assert top.sweep_result.run_id == "run-high"  # the higher-Sharpe candidate ranked first
        assert top.sweep_result.metrics["sharpe_ratio"] == 5.0
        assert top.sweep_result.strategy_code  # real generated code, not blank
        assert top.params == {"fast_period": 10, "slow_period": 40}

    @pytest.mark.asyncio
    async def test_completeness_reflects_requested_grid_size_not_attempted(self) -> None:
        """10-point grid, 2 points fail to parameterize -- completeness
        must be 8/10 = 0.8, not 1.0 computed against a silently-shrunk
        denominator of 8."""
        mock_tools = AsyncMock()

        async def _run_backtest(**kwargs):
            params = kwargs.get("indicators")  # unused, just documenting signature
            return _bt_result("run-ok", sharpe=1.0)

        # 8 succeed, 2 fail (unknown recipe key on those specific points,
        # simulated by making run_backtest itself the failure point isn't
        # possible per-point without inspecting params -- so raise from
        # run_backtest via side_effect for exactly 2 calls instead).
        results = [_bt_result(f"run-{i}", sharpe=float(i)) for i in range(8)]
        mock_tools.run_backtest.side_effect = results[:2] + [RuntimeError("simulator rejected candidate")] + results[2:5] + [RuntimeError("simulator rejected candidate")] + results[5:]

        grid = [{"fast_period": 5 + i, "slow_period": 40} for i in range(10)]
        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=grid, tools=mock_tools,
        )

        assert result.requested == 10
        assert result.succeeded == 8
        assert result.completeness == 0.8
        assert len(result.ranked) == 8

    @pytest.mark.asyncio
    async def test_grid_size_cap_bounds_a_single_round(self) -> None:
        mock_tools = AsyncMock()
        oversized_grid = [{"fast_period": i, "slow_period": 40} for i in range(MAX_GRID_POINTS + 1)]

        with pytest.raises(GridTooLargeError):
            await run_sweep_grid(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid=oversized_grid, tools=mock_tools,
            )
        mock_tools.run_backtest.assert_not_awaited()  # rejected before running anything

    @pytest.mark.asyncio
    async def test_pbo_computed_across_successful_candidates(self) -> None:
        mock_tools = AsyncMock()
        rng = np.random.default_rng(42)
        returns_a = rng.normal(0.001, 0.01, 200).tolist()
        returns_b = rng.normal(0.0005, 0.01, 200).tolist()
        mock_tools.run_backtest.side_effect = [
            _bt_result("run-a", sharpe=1.2, daily_returns=returns_a),
            _bt_result("run-b", sharpe=0.8, daily_returns=returns_b),
        ]
        grid = [{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}]

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=grid, tools=mock_tools,
        )

        assert result.pbo is not None
        assert 0.0 <= result.pbo["pbo"] <= 1.0

    @pytest.mark.asyncio
    async def test_pbo_is_none_with_fewer_than_two_successful_candidates(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = [_bt_result("run-a", sharpe=1.2, daily_returns=[0.01] * 50)]

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", param_grid=[{"fast_period": 5, "slow_period": 40}], tools=mock_tools,
        )

        assert result.pbo is None

    @pytest.mark.asyncio
    async def test_empty_grid_rejected(self) -> None:
        mock_tools = AsyncMock()
        with pytest.raises(ValueError, match="at least one"):
            await run_sweep_grid(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid=[], tools=mock_tools,
            )

    @pytest.mark.asyncio
    async def test_both_modes_specified_rejected(self) -> None:
        mock_tools = AsyncMock()
        with pytest.raises(ValueError, match="exactly one"):
            await run_sweep_grid(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", base_code="class X: pass", param_grid=[{"a": 1}], tools=mock_tools,
            )


class TestRunSweepGridBaseCodeMode:
    @pytest.mark.asyncio
    async def test_base_code_mode_requires_param_name(self) -> None:
        mock_tools = AsyncMock()
        with pytest.raises(ValueError, match="param_name"):
            await run_sweep_grid(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                base_code="class X:\n    y = 1\n", param_grid=[{"y": 5}], tools=mock_tools,
            )

    @pytest.mark.asyncio
    async def test_base_code_mode_runs_each_grid_point(self) -> None:
        mock_tools = AsyncMock()
        mock_tools.run_backtest.side_effect = [
            _bt_result("run-1", sharpe=1.0), _bt_result("run-2", sharpe=2.0),
        ]
        code = "class X:\n    fast_period = 20\n"

        result = await run_sweep_grid(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            base_code=code, param_name="fast_period",
            param_grid=[{"fast_period": 5}, {"fast_period": 10}],
            tools=mock_tools,
        )

        assert result.succeeded == 2
        assert mock_tools.run_backtest.await_count == 2
