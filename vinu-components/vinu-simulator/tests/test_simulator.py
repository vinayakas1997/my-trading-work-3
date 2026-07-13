from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_simulator.engine.simulator import WeightSimulator, SimulatorEnv
from vinu_simulator.models.simulation import SimulationInput


class TestWeightSimulator:
    def test_run_basic(self, synthetic_prices, synthetic_weights, sim_config):
        inp = SimulationInput(
            strategy_name="test",
            weight_signals=synthetic_weights,
            price_data=synthetic_prices,
            config=sim_config,
        )
        sim = WeightSimulator(sim_config)
        result = sim.run(inp)

        assert result.strategy_name == "test"
        assert len(result.portfolio_values) > 0
        assert len(result.daily_returns) > 0
        assert result.metrics["total_return"] != 0.0
        assert result.metrics["sharpe_ratio"] != 0.0
        assert "AAPL" in result.weights_history.columns
        assert len(result.trades) > 0

    def test_run_empty_weights_raises(self, synthetic_prices, sim_config):
        empty_weights = pd.DataFrame()
        inp = SimulationInput(
            strategy_name="test",
            weight_signals=empty_weights,
            price_data=synthetic_prices,
            config=sim_config,
        )
        sim = WeightSimulator(sim_config)
        import pytest
        with pytest.raises(ValueError, match="No common tickers"):
            sim.run(inp)

    def test_run_no_common_tickers(self, synthetic_prices, synthetic_weights, sim_config):
        prices = synthetic_prices.rename(
            columns={"AAPL": "AAPL2", "MSFT": "MSFT2", "SPY": "SPY2"}
        )
        inp = SimulationInput(
            strategy_name="test",
            weight_signals=synthetic_weights,
            price_data=prices,
            config=sim_config,
        )
        sim = WeightSimulator(sim_config)
        import pytest
        with pytest.raises(ValueError, match="No common tickers"):
            sim.run(inp)

    def test_result_has_all_metrics(self, synthetic_prices, synthetic_weights, sim_config):
        inp = SimulationInput(
            strategy_name="test",
            weight_signals=synthetic_weights,
            price_data=synthetic_prices,
            config=sim_config,
        )
        sim = WeightSimulator(sim_config)
        result = sim.run(inp)

        required = [
            "total_return", "cagr", "annual_volatility",
            "sharpe_ratio", "sortino_ratio", "max_drawdown",
            "calmar_ratio", "win_rate", "skewness", "kurtosis",
        ]
        for key in required:
            assert key in result.metrics, f"Missing metric: {key}"

    def test_equity_curve_monotonic_dates(self, synthetic_prices, synthetic_weights, sim_config):
        inp = SimulationInput(
            strategy_name="test",
            weight_signals=synthetic_weights,
            price_data=synthetic_prices,
            config=sim_config,
        )
        sim = WeightSimulator(sim_config)
        result = sim.run(inp)
        assert result.portfolio_values.index.is_monotonic_increasing


class TestSimulatorEnv:
    def test_reset_returns_state(self, synthetic_prices, sim_config):
        env = SimulatorEnv(
            tickers=["AAPL", "MSFT", "SPY"],
            price_data=synthetic_prices,
            config=sim_config,
        )
        state = env.reset()
        n_tickers = len(env.tickers)
        assert len(state) == n_tickers + 1 + n_tickers  # weights + cash + prices
        assert env.cash == sim_config.initial_capital
        assert env.portfolio_value == sim_config.initial_capital

    def test_step_updates_portfolio(self, synthetic_prices, sim_config):
        env = SimulatorEnv(
            tickers=["AAPL", "MSFT", "SPY"],
            price_data=synthetic_prices,
            config=sim_config,
        )
        env.reset()
        target = np.array([0.5, 0.3, 0.2])
        state, reward, done, info = env.step(target)
        assert not np.isnan(reward)
        assert isinstance(done, bool)
        n_tickers = len(env.tickers)
        assert len(state) == n_tickers + 1 + n_tickers

    def test_step_until_done(self, synthetic_prices, sim_config):
        env = SimulatorEnv(
            tickers=["AAPL", "MSFT", "SPY"],
            price_data=synthetic_prices,
            config=sim_config,
        )
        env.reset()
        done = False
        steps = 0
        while not done and steps < 100:
            target = np.array([0.5, 0.3, 0.2])
            _, _, done, _ = env.step(target)
            steps += 1
        assert done
        assert steps > 0

    def test_equity_curve_after_steps(self, synthetic_prices, sim_config):
        env = SimulatorEnv(
            tickers=["AAPL", "MSFT", "SPY"],
            price_data=synthetic_prices,
            config=sim_config,
        )
        env.reset()
        for _ in range(5):
            target = np.array([0.5, 0.3, 0.2])
            env.step(target)
        curve = env.equity_curve
        assert len(curve) == 6  # initial + 5 steps

    def test_metrics_after_run(self, synthetic_prices, sim_config):
        env = SimulatorEnv(
            tickers=["AAPL", "MSFT", "SPY"],
            price_data=synthetic_prices,
            config=sim_config,
        )
        env.reset()
        for _ in range(10):
            target = np.array([0.5, 0.3, 0.2])
            env.step(target)
        metrics = env.metrics()
        for key in ["total_return", "cagr", "sharpe_ratio", "max_drawdown"]:
            assert key in metrics
