from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from vinu_simulator.engine.attribution import beta_regression, by_exit_reason_stats, by_symbol_stats, match_trades
from vinu_simulator.engine.regime import classify_regime, per_regime_performance
from vinu_simulator.engine.validation import (
    bootstrap_sharpe_ci,
    monte_carlo_permutation,
    walk_forward_consistency,
)


@dataclass
class _FakeTrade:
    symbol: str
    side: str
    shares: float
    price: float
    cost: float
    date: datetime = None
    trade_id: str = ""

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now()


class TestBySymbolStats:
    def test_aggregates_by_symbol(self):
        trades = [
            _FakeTrade("AAPL", "BUY", 100, 150.0, 5.0, trade_id="t1"),
            _FakeTrade("AAPL", "SELL", 100, 160.0, 5.0, trade_id="t2"),
            _FakeTrade("MSFT", "BUY", 200, 300.0, 10.0, trade_id="t3"),
            _FakeTrade("MSFT", "SELL", 200, 310.0, 10.0, trade_id="t4"),
        ]
        stats = by_symbol_stats(trades)
        assert "AAPL" in stats
        assert stats["AAPL"]["count"] == 1
        expected_pnl = (160.0 - 150.0) * 100.0 - 5.0 - 5.0
        assert stats["AAPL"]["total_pnl"] == expected_pnl

        assert "MSFT" in stats
        assert stats["MSFT"]["count"] == 1
        expected_msft_pnl = (310.0 - 300.0) * 200.0 - 10.0 - 10.0
        assert stats["MSFT"]["total_pnl"] == expected_msft_pnl


class TestByExitReasonStats:
    def test_groups_by_exit_reason(self):
        trades = [
            _FakeTrade("AAPL", "BUY", 100, 150.0, 5.0, trade_id="t1"),
            _FakeTrade("AAPL", "SELL", 100, 160.0, 5.0, trade_id="t2"),
            _FakeTrade("MSFT", "BUY", 50, 300.0, 3.0, trade_id="t3"),
            _FakeTrade("MSFT", "SELL", 50, 290.0, 3.0, trade_id="t4"),
        ]
        reasons = {"t2": "take_profit", "t4": "stop_loss"}
        stats = by_exit_reason_stats(trades, reasons)
        assert "take_profit" in stats
        assert stats["take_profit"]["count"] == 1
        assert "stop_loss" in stats
        assert stats["stop_loss"]["count"] == 1


class TestBetaRegression:
    def test_computes_alpha_beta(self):
        strat = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005] * 10)
        bench = pd.Series([0.008, 0.015, -0.005, 0.01, 0.003] * 10)
        result = beta_regression(strat, bench)
        assert "alpha" in result
        assert "beta" in result
        assert result["n_observations"] == 50

    def test_requires_minimum_observations(self):
        strat = pd.Series([0.01, 0.02, 0.03])
        bench = pd.Series([0.01, 0.015, 0.02])
        result = beta_regression(strat, bench)
        assert result == {}


class TestRegimeAnalysis:
    def test_classify_regime(self):
        returns = pd.Series([0.02, -0.02, 0.005, 0.03, -0.015, 0.001, 0.05, -0.03, 0.002, 0.001] * 10)
        regimes = classify_regime(returns)
        assert len(regimes) == len(returns)
        assert all(r in ("bull", "bear", "sideways", "high_vol") for r in regimes)

    def test_per_regime_performance(self):
        returns = pd.Series([0.02, -0.02, 0.01, 0.03, -0.01] * 10)
        regimes = pd.Series(["bull", "bear", "bull", "bull", "bear"] * 10)
        perf = per_regime_performance(returns, regimes)
        assert "bull" in perf
        assert "bear" in perf
        assert perf["bull"]["count"] == 30
        assert perf["bear"]["count"] == 20


class TestMonteCarloPermutation:
    def test_rejects_random_trades(self):
        pnls = [1.0, -0.5, 0.8, -0.3, 1.2, -0.7, 0.5, -0.2]
        actual_sharpe = 0.5
        result = monte_carlo_permutation(pnls, actual_sharpe, n_iterations=100)
        assert "p_value" in result
        assert result["n_trades"] == 8
        assert result["minimum_met"] is True

    def test_requires_minimum_trades(self):
        result = monte_carlo_permutation([1.0, -0.5], 0.5)
        assert result["minimum_met"] is False
        assert result["p_value"] == 1.0


class TestBootstrapSharpeCI:
    def test_computes_confidence_interval(self):
        returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015, 0.005, -0.008, 0.012, 0.007, -0.003] * 5)
        result = bootstrap_sharpe_ci(returns, n_iterations=100)
        assert "ci_low" in result
        assert "ci_high" in result
        assert result["ci_low"] <= result["ci_high"]
        assert result["minimum_met"] is True

    def test_requires_minimum_observations(self):
        returns = pd.Series([0.01, 0.02, 0.03])
        result = bootstrap_sharpe_ci(returns)
        assert result["minimum_met"] is False


class TestWalkForwardConsistency:
    def test_computes_consistency(self):
        equity = pd.Series([1.0, 1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.18, 1.2, 1.25] * 5)
        result = walk_forward_consistency(equity, n_windows=5)
        assert "consistency_rate" in result
        assert result["total_windows"] == 5
        assert result["minimum_met"] is True

    def test_requires_sufficient_data(self):
        equity = pd.Series([1.0, 1.05, 1.1])
        result = walk_forward_consistency(equity, n_windows=5)
        assert result["minimum_met"] is False
