from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.historical_simulation import (
    compute_performance_metrics,
    run_historical_simulation,
)
from vinu_portfolio.service import PortfolioService


def _service() -> PortfolioService:
    return PortfolioService(config=PortfolioConfig())


def _synthetic_returns(n_days: int = 300, n_strategies: int = 3, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    cols = {f"s{i}": rng.normal(0.0005, 0.01, n_days) for i in range(n_strategies)}
    return pd.DataFrame(cols, index=dates)


def _strategies(n: int = 3) -> list[dict]:
    return [{"name": f"s{i}", "kind": "yaml"} for i in range(n)]


class TestComputePerformanceMetrics:
    def test_empty_series_returns_zeroed_metrics(self) -> None:
        m = compute_performance_metrics(pd.Series(dtype=float))
        assert m.sharpe == 0.0
        assert m.n_days == 0

    def test_all_positive_returns_has_zero_drawdown_and_full_win_rate(self) -> None:
        s = pd.Series([0.01] * 50)
        m = compute_performance_metrics(s)
        assert m.max_drawdown == 0.0
        assert m.win_rate == 1.0
        assert m.n_days == 50

    def test_pnl_matches_manual_compounding(self) -> None:
        s = pd.Series([0.1, -0.05, 0.02])
        m = compute_performance_metrics(s)
        expected_total = (1.1 * 0.95 * 1.02) - 1.0
        assert m.total_return == pytest.approx(round(expected_total, 4), abs=1e-4)

    def test_a_loss_produces_negative_drawdown_and_partial_win_rate(self) -> None:
        s = pd.Series([0.05, -0.10, 0.03, -0.02, 0.04])
        m = compute_performance_metrics(s)
        assert m.max_drawdown < 0.0
        assert 0.0 < m.win_rate < 1.0


class TestRunHistoricalSimulation:
    def test_empty_returns_df_yields_empty_status(self) -> None:
        svc = _service()
        result = run_historical_simulation(_strategies(), pd.DataFrame(), pd.Series(dtype=float), svc)
        assert result.status == "empty"

    def test_no_strategies_yields_empty_status(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns()
        result = run_historical_simulation([], returns_df, returns_df["s0"], svc)
        assert result.status == "empty"

    def test_too_few_observations_yields_empty_status(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns(n_days=10)
        result = run_historical_simulation(_strategies(), returns_df, returns_df["s0"], svc, warmup_days=21)
        assert result.status == "empty"

    def test_runs_without_error_and_produces_daily_records(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns(n_days=300)
        benchmark = returns_df["s0"]
        result = run_historical_simulation(_strategies(), returns_df, benchmark, svc)
        assert result.status == "ok"
        assert result.n_days > 0
        assert len(result.daily_records) == result.n_days

    def test_weights_sum_to_one_every_day(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns(n_days=300)
        benchmark = returns_df["s0"]
        result = run_historical_simulation(_strategies(), returns_df, benchmark, svc)
        for record in result.daily_records:
            total = sum(record["weights"].values())
            # weights are rounded to 4dp for the record, so tolerate that
            # rounding, not exact float equality
            assert total == pytest.approx(1.0, abs=1e-3)

    def test_no_nan_positions_or_returns(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns(n_days=300)
        benchmark = returns_df["s0"]
        result = run_historical_simulation(_strategies(), returns_df, benchmark, svc)
        for record in result.daily_records:
            assert not any(pd.isna(w) for w in record["weights"].values())
            assert not pd.isna(record["portfolio_return"])
        for metrics in (result.strategy_metrics, result.equal_weight_metrics, result.benchmark_metrics):
            assert not any(pd.isna(v) for v in metrics.values() if isinstance(v, float))

    def test_portfolio_return_matches_weights_dot_realized_returns(self) -> None:
        svc = _service()
        returns_df = _synthetic_returns(n_days=300)
        benchmark = returns_df["s0"]
        result = run_historical_simulation(_strategies(), returns_df, benchmark, svc)
        # Recompute the first day's realized return directly from its
        # recorded weights and the actual returns_df row, independent of
        # the simulator's own bookkeeping.
        first = result.daily_records[0]
        # Locate the actual next business day present in the index instead
        # of assuming exact BDay arithmetic matches the DataFrame's index.
        dates = list(returns_df.index)
        as_of_idx = dates.index(pd.Timestamp(result.start_date))
        realize_date = dates[as_of_idx + 1]
        realized_row = returns_df.loc[realize_date]
        expected = sum(w * float(realized_row[name]) for name, w in first["weights"].items())
        assert first["portfolio_return"] == pytest.approx(round(expected, 6), abs=1e-5)

    def test_zero_variance_strategy_returns_fall_back_gracefully(self) -> None:
        svc = _service()
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        returns_df = pd.DataFrame({
            "s0": [0.0] * 100,
            "s1": [0.0] * 100,
        }, index=dates)
        result = run_historical_simulation(_strategies(2), returns_df, returns_df["s0"], svc, warmup_days=21)
        assert result.status == "ok"
        for record in result.daily_records:
            assert sum(record["weights"].values()) == pytest.approx(1.0, abs=1e-6)
