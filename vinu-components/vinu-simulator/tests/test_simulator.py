from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

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


class TestPositionSizingIntegration:
    """
    Proves position sizing is actually wired into the live engine, not just unit
    tested in isolation: the same target-weight signal, run through the same price
    data, must produce a smaller realized position during a high-volatility period
    under vol_target sizing than under the default fixed sizing.
    """

    def _build_input(self, position_sizing_model: str) -> tuple[SimulationInput, SimulationConfig]:
        rng = np.random.default_rng(7)
        n = 40
        dates = pd.date_range("2023-01-02", periods=n, freq="D")

        # Calm for the first 25 days, then a volatility spike for the rest — enough
        # history accumulates (vol_lookback_days=20) partway through the spike for
        # the sizer to react to it within this same backtest.
        calm = rng.normal(0, 0.002, 20)
        volatile = rng.normal(0, 0.06, n - 20)
        daily_returns = np.concatenate([calm, volatile])
        prices = 100.0 * np.cumprod(1 + daily_returns)

        price_df = pd.DataFrame({"X": prices}, index=dates)
        # Constant full-long target every day so any change in realized weight is
        # attributable to sizing, not to the signal itself changing.
        weights_df = pd.DataFrame({"X": np.ones(n)}, index=dates)

        config = SimulationConfig(
            strategy_name="sizing_test",
            start_date=str(dates[0].date()),
            end_date=str(dates[-1].date()),
            initial_capital=1_000_000.0,
            transaction_cost_pct=0.0,
            slippage_pct=0.0,
            slippage_model="flat",
            deviation_threshold=0.0,
            position_sizing_model=position_sizing_model,
            target_annual_vol=0.15,
            vol_lookback_days=20,
            max_leverage=1.0,
        )
        inp = SimulationInput(
            strategy_name="sizing_test",
            weight_signals=weights_df,
            price_data=price_df,
            config=config,
        )
        return inp, config

    def test_vol_target_shrinks_exposure_during_volatility_spike(self):
        fixed_inp, _ = self._build_input("fixed")
        vol_target_inp, _ = self._build_input("vol_target")

        fixed_result = WeightSimulator(fixed_inp.config).run(fixed_inp)
        vol_target_result = WeightSimulator(vol_target_inp.config).run(vol_target_inp)

        # Look at the tail, well after the vol spike has populated the lookback
        # window (spike starts at day 20, lookback is 20 days).
        fixed_tail_weight = fixed_result.weights_history["X"].iloc[-10:].abs().mean()
        vol_target_tail_weight = vol_target_result.weights_history["X"].iloc[-10:].abs().mean()

        assert fixed_tail_weight == pytest.approx(1.0, abs=0.05)
        assert vol_target_tail_weight < fixed_tail_weight


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


class TestExecutionRealism:
    """Stage A (A28/A30): volume-cap visibility + broker-reject probability."""

    def _daily(self, n: int = 12):
        dates = pd.date_range("2023-01-02", periods=n, freq="D")
        prices = pd.DataFrame(
            {"X": np.linspace(100.0, 110.0, n), "Y": np.linspace(50.0, 55.0, n)},
            index=dates,
        )
        # one rebalance signal on day 0, forward-filled
        weights = pd.DataFrame({"X": [0.5], "Y": [0.5]}, index=[dates[0]])
        return dates, prices, weights

    def _config(self, **kw) -> SimulationConfig:
        base = dict(
            strategy_name="exec_realism",
            start_date="2023-01-02",
            end_date="2023-01-31",
            initial_capital=1_000_000.0,
            transaction_cost_pct=0.0,
            slippage_pct=0.0,
            slippage_model="flat",
            allow_short=False,
            deviation_threshold=0.0,
        )
        base.update(kw)
        return SimulationConfig(**base)

    def test_volume_cap_is_flagged_on_the_trade_and_counted(self):
        dates, prices, weights = self._daily()
        # Y has almost no volume -> its buy gets clipped hard; X has plenty.
        volume = pd.DataFrame({"X": [1e9] * len(dates), "Y": [1.0] * len(dates)}, index=dates)
        config = self._config(max_pct_of_volume=0.1)
        inp = SimulationInput("exec_realism", weights, prices, config, volume_data=volume)
        result = WeightSimulator(config).run(inp)

        capped = [t for t in result.trades if t.volume_capped]
        assert capped, "expected at least one volume-capped fill"
        assert all(t.symbol == "Y" for t in capped)
        assert result.metrics["volume_capped_fills"] == float(len(capped))

    def test_no_volume_cap_when_limit_is_one(self):
        dates, prices, weights = self._daily()
        volume = pd.DataFrame({"X": [1.0], "Y": [1.0]}, index=[dates[0]]).reindex(dates).ffill()
        config = self._config(max_pct_of_volume=1.0)
        inp = SimulationInput("exec_realism", weights, prices, config, volume_data=volume)
        result = WeightSimulator(config).run(inp)
        assert result.metrics["volume_capped_fills"] == 0.0
        assert all(not t.volume_capped for t in result.trades)

    def test_reject_prob_one_drops_every_fill(self):
        dates, prices, weights = self._daily()
        config = self._config(execution_reject_prob=1.0)
        inp = SimulationInput("exec_realism", weights, prices, config)
        result = WeightSimulator(config).run(inp)
        assert result.trades == []
        assert result.metrics["rejected_fills"] > 0.0

    def test_reject_prob_zero_is_unchanged_and_deterministic(self):
        dates, prices, weights = self._daily()
        a = WeightSimulator(self._config()).run(
            SimulationInput("exec_realism", weights, prices, self._config())
        )
        b = WeightSimulator(self._config()).run(
            SimulationInput("exec_realism", weights, prices, self._config())
        )
        assert a.metrics["rejected_fills"] == 0.0
        assert len(a.trades) == len(b.trades)
        assert a.metrics["total_return"] == b.metrics["total_return"]

    def test_same_seed_reproduces_partial_rejects(self):
        n = 40
        dates = pd.date_range("2023-01-02", periods=n, freq="D")
        rng = np.random.default_rng(3)
        # volatile prices so the portfolio drifts off target every bar and each
        # rebalance actually trades -> many reject opportunities for a 50% rate
        px = 100.0 * np.cumprod(1 + rng.normal(0, 0.03, n))
        py = 50.0 * np.cumprod(1 + rng.normal(0, 0.03, n))
        prices = pd.DataFrame({"X": px, "Y": py}, index=dates)
        wk = pd.date_range(dates[0], dates[-1], freq="2D")
        weights = pd.DataFrame({"X": [0.5] * len(wk), "Y": [0.5] * len(wk)}, index=wk)

        def run(seed: int):
            cfg = self._config(execution_reject_prob=0.5, random_seed=seed,
                               deviation_threshold=0.001)
            return WeightSimulator(cfg).run(SimulationInput("exec_realism", weights, prices, cfg))

        r1, r1b, r2 = run(1), run(1), run(2)
        # same seed -> byte-identical outcome
        assert r1.metrics["rejected_fills"] == r1b.metrics["rejected_fills"]
        assert r1.metrics["total_return"] == r1b.metrics["total_return"]
        # a 50% reject rate over many bars does drop fills
        assert r1.metrics["rejected_fills"] > 0.0
        # different seed -> a different reject pattern -> a different equity path
        # (the reject counts can collide; the realized return won't)
        assert r2.metrics["total_return"] != r1.metrics["total_return"]
