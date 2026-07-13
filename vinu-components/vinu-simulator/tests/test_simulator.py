from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_simulator.engine.simulator import WeightSimulator, SimulatorEnv
from vinu_simulator.models.simulation import SimulationConfig, SimulationInput


class TestNoLookAheadExecution:
    """
    A signal observed using data through day D can only be acted on starting day D+1 —
    the engine must never fill a trade at the exact price that produced the signal.
    """

    def test_signal_executes_one_day_later_at_next_price(self):
        dates = pd.date_range("2023-01-02", periods=4, freq="D")
        prices = pd.DataFrame({"X": [100.0, 105.0, 110.0, 120.0]}, index=dates)
        # A single signal set on day 0 only — forward-filled from there on.
        weights = pd.DataFrame({"X": [1.0]}, index=[dates[0]])
        config = SimulationConfig(
            strategy_name="lookahead_test",
            start_date=str(dates[0].date()),
            end_date=str(dates[-1].date()),
            initial_capital=1_000_000.0,
            transaction_cost_pct=0.0,
            slippage_pct=0.0,
            slippage_model="flat",
            deviation_threshold=0.0,
        )
        inp = SimulationInput(
            strategy_name="lookahead_test",
            weight_signals=weights,
            price_data=prices,
            config=config,
        )
        result = WeightSimulator(config).run(inp)

        assert len(result.trades) == 1
        first_trade = result.trades[0]
        # Must fill at day 1's price (105), never at day 0's price (100) — the price
        # that produced the signal.
        assert first_trade.date == dates[1]
        assert first_trade.price == 105.0
        # No position exists on day 0 — the engine had nothing to act on yet.
        assert result.weights_history.iloc[0]["X"] == 0.0


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
