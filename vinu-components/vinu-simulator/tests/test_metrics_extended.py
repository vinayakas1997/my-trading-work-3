from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.engine.metrics import (
    compute_extended_metrics,
    compute_full_metrics,
    compute_performance_metrics,
)


def _make_returns(daily_rets: list[float]) -> tuple[pd.Series, pd.Series]:
    port = (1 + pd.Series(daily_rets)).cumprod() * 1_000_000
    rets = pd.Series(daily_rets)
    return port, rets


class TestVaR:
    def test_var_95_negative_when_losses_exist(self):
        port, rets = _make_returns([0.01, -0.02, 0.005, -0.015, -0.03, 0.02, -0.01, 0.015, -0.025, -0.005])
        ext = compute_extended_metrics(port, rets)
        assert ext["var_95"] < 0

    def test_var_99_is_more_negative_than_var_95(self):
        port, rets = _make_returns([0.01, -0.02, 0.005, -0.015, -0.03, 0.02, -0.01, 0.015, -0.025, -0.005])
        ext = compute_extended_metrics(port, rets)
        assert ext["var_99"] <= ext["var_95"]


class TestCVaR:
    def test_cvar_95_is_below_var_95(self):
        rets = [0.01, -0.02, -0.04, -0.06, 0.02, -0.03, 0.015, -0.05, 0.005, -0.01]
        port, rets_s = _make_returns(rets)
        ext = compute_extended_metrics(port, rets_s)
        assert ext["cvar_95"] <= ext["var_95"]


class TestDrawdownCharacteristics:
    def test_max_dd_duration_is_positive(self):
        port, rets = _make_returns([-0.01, -0.02, -0.015, 0.01, 0.02, -0.01, -0.03, 0.05, 0.01, 0.02])
        ext = compute_extended_metrics(port, rets)
        assert ext["max_dd_duration_days"] >= 0

    def test_recovery_time_is_positive(self):
        port, rets = _make_returns([-0.05, -0.03, 0.01, 0.02, 0.03, 0.04, 0.01, 0.02, 0.01, 0.005])
        ext = compute_extended_metrics(port, rets)
        assert ext["recovery_time_days"] >= 0

    def test_avg_drawdown_is_negative_when_losses(self):
        port, rets = _make_returns([-0.01, -0.02, -0.015, 0.01, 0.02])
        ext = compute_extended_metrics(port, rets)
        assert ext["avg_drawdown"] <= 0


class TestProfitFactor:
    def test_profit_factor_greater_than_one_when_profitable(self):
        port, rets = _make_returns([0.02, -0.01, 0.03, -0.005, 0.015])
        ext = compute_extended_metrics(port, rets)
        assert ext["profit_factor"] > 1.0

    def test_profit_factor_less_than_one_when_unprofitable(self):
        rets = [0.01, -0.05, -0.03, 0.005, -0.04]
        port, rets_s = _make_returns(rets)
        ext = compute_extended_metrics(port, rets_s)
        assert ext["profit_factor"] < 1.0


class TestWinRateAndAvgWinLoss:
    def test_avg_win_pct_positive(self):
        port, rets = _make_returns([0.02, -0.01, 0.03, -0.005, 0.015])
        ext = compute_extended_metrics(port, rets)
        assert ext["avg_win_pct"] > 0

    def test_avg_loss_pct_negative(self):
        port, rets = _make_returns([0.02, -0.01, 0.03, -0.005, 0.015])
        ext = compute_extended_metrics(port, rets)
        assert ext["avg_loss_pct"] < 0

    def test_hit_rate_between_0_and_1(self):
        port, rets = _make_returns([0.02, -0.01, 0.03, -0.005, 0.015])
        ext = compute_extended_metrics(port, rets)
        assert 0 <= ext["hit_rate"] <= 1


class TestTurnover:
    def test_turnover_computed_with_trades(self):
        port, rets = _make_returns([0.01] * 252)
        trades = [
            {"shares": 1000, "price": 150},
            {"shares": -500, "price": 155},
        ]
        ext = compute_extended_metrics(port, rets, trades=trades)
        assert ext["annual_turnover"] > 0

    def test_turnover_zero_without_trades(self):
        port, rets = _make_returns([0.01] * 252)
        ext = compute_extended_metrics(port, rets, trades=[])
        assert ext["annual_turnover"] == 0.0


class TestSharpeSignificance:
    def test_sharpe_standard_error_positive(self):
        np.random.seed(42)
        rets = np.random.normal(0.0005, 0.01, 252)
        port, rets_s = _make_returns(rets.tolist())
        ext = compute_extended_metrics(port, rets_s)
        assert ext["sharpe_standard_error"] > 0
        assert ext["sharpe_p_value"] > 0
        assert ext["sharpe_ci_95_low"] < ext["sharpe_ci_95_high"]


class TestBenchmarkMetrics:
    def test_beta_around_one_when_correlated(self):
        np.random.seed(42)
        common = np.random.normal(0.0005, 0.01, 252)
        strat = common + np.random.normal(0, 0.002, 252)
        bench = common + np.random.normal(0, 0.001, 252)
        port, rets_s = _make_returns(strat.tolist())
        bench_s = pd.Series(bench)
        ext = compute_extended_metrics(port, rets_s, benchmark_returns=bench_s)
        assert 0.5 <= ext["beta"] <= 1.5
        assert ext["market_correlation"] > 0.5

    def test_alpha_positive_when_strategy_outperforms(self):
        np.random.seed(42)
        strat = np.random.normal(0.001, 0.01, 252)
        bench = np.random.normal(0.0003, 0.01, 252)
        port, rets_s = _make_returns(strat.tolist())
        bench_s = pd.Series(bench)
        ext = compute_extended_metrics(port, rets_s, benchmark_returns=bench_s)
        assert ext["alpha"] > 0

    def test_tracking_error_positive(self):
        np.random.seed(42)
        strat = np.random.normal(0.0005, 0.015, 252)
        bench = np.random.normal(0.0005, 0.01, 252)
        port, rets_s = _make_returns(strat.tolist())
        bench_s = pd.Series(bench)
        ext = compute_extended_metrics(port, rets_s, benchmark_returns=bench_s)
        assert ext["tracking_error"] > 0

    def test_benchmark_metrics_skipped_when_no_benchmark(self):
        port, rets = _make_returns([0.01] * 100)
        ext = compute_extended_metrics(port, rets)
        assert "beta" not in ext
        assert "alpha" not in ext


class TestFullMetrics:
    def test_full_metrics_includes_basic_and_extended(self):
        port, rets = _make_returns([0.01, -0.005, 0.02, -0.01, 0.015] * 50)
        full = compute_full_metrics(port, rets)
        assert "sharpe_ratio" in full
        assert "var_95" in full
        assert "cvar_95" in full
        assert "profit_factor" in full

    def test_full_metrics_basic_values_match(self):
        port, rets = _make_returns([0.01] * 100)
        basic = compute_performance_metrics(port, rets)
        full = compute_full_metrics(port, rets)
        assert full["sharpe_ratio"] == basic["sharpe_ratio"]
        assert full["total_return"] == basic["total_return"]
        assert full["max_drawdown"] == basic["max_drawdown"]
