from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.engine.custom_sim import simulate_custom
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.models.simulation import SimulationConfig


class _ConstantWeightStrategy(BaseStrategy):
    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(0.5, index=data.index)


def _make_ohlcv(dates: pd.DatetimeIndex, closes: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(len(dates), 1_000_000.0),
        },
        index=dates,
    )


@pytest.fixture
def sim_config() -> SimulationConfig:
    return SimulationConfig(
        strategy_name="test",
        start_date="2023-01-01",
        end_date="2023-01-20",
        initial_capital=1_000_000.0,
    )


class TestNoLookAheadOnMissingData:
    def test_leading_nan_symbol_raises_instead_of_backfilling(self, sim_config):
        """
        A symbol with no price data before its first real trading day must not have
        that gap silently filled with a future price (bfill). The engine should raise
        instead of running a backtest on leaked data.
        """
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        full_closes = 100.0 + np.arange(len(dates), dtype=float)

        ohclv_data = {
            "AAA": _make_ohlcv(dates, full_closes),
            "BBB": _make_ohlcv(dates, full_closes * 2),
        }
        # BBB has no real trades for its first 3 sessions — a genuine data gap,
        # not a value that should be back-filled from later dates.
        ohclv_data["BBB"].loc[dates[:3], ["open", "high", "low", "close"]] = np.nan

        with pytest.raises(ValueError, match="NaN"):
            simulate_custom(
                strategy_class=_ConstantWeightStrategy,
                symbols=["AAA", "BBB"],
                ohclv_data=ohclv_data,
                sim_config=sim_config,
            )

    def test_no_gaps_runs_cleanly(self, sim_config):
        """Sanity check: without a leading gap, the same strategy runs fine end to end."""
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        full_closes = 100.0 + np.arange(len(dates), dtype=float)
        ohclv_data = {
            "AAA": _make_ohlcv(dates, full_closes),
            "BBB": _make_ohlcv(dates, full_closes * 2),
        }
        result = simulate_custom(
            strategy_class=_ConstantWeightStrategy,
            symbols=["AAA", "BBB"],
            ohclv_data=ohclv_data,
            sim_config=sim_config,
        )
        assert len(result.portfolio_values) > 0


class _CheatingPerfectForesightStrategy(BaseStrategy):
    """
    'Cheats' by reading tomorrow's close directly out of the in-memory DataFrame —
    only possible because generate_weights receives the entire date range at once,
    not a streaming/online feed. This exists purely to prove that look-ahead safety
    comes from the ENGINE's execution delay, not from strategy discipline: a
    strategy with literal perfect knowledge of tomorrow's direction must still be
    unable to profit from it, because the engine only lets it act a day late.
    """

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        future_up = data["close"].shift(-1) > data["close"]
        return future_up.astype(float) * 0.98


class _CrashingStrategy(BaseStrategy):
    """Crashes on a missing/NaN indicator column -- e.g. a features fetch that
    silently returned None upstream (see #32) and dropped a column the
    strategy relies on."""

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        return (data["rsi_14"] > 50).astype(float)  # KeyError: column absent


class TestGenerateWeightsCrashIsDistinguishableFromLegitimateZeroTrades:
    """
    #31: a strategy that crashes in generate_weights must not be silently
    indistinguishable from one that legitimately chose to trade zero times --
    both used to produce an identical all-zero-weight, trade_count==0 result.
    """

    def test_crash_is_recorded_in_diagnostics(self, sim_config):
        # Two symbols: BBB gets the indicator column it needs and trades
        # normally; AAA doesn't and crashes. Mirrors #32 composing with #31 --
        # a missing-indicator-driven crash must still be flagged as a crash,
        # and having one healthy symbol must not hide the other's crash (and
        # must not itself trip the module's "no weight data at all" guard).
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        closes = 100.0 + np.arange(len(dates), dtype=float)
        ohclv_data = {
            "AAA": _make_ohlcv(dates, closes),
            "BBB": _make_ohlcv(dates, closes * 2),
        }
        indicator_data = {"BBB": pd.DataFrame({"rsi_14": [60.0] * len(dates)}, index=dates)}

        result = simulate_custom(
            strategy_class=_CrashingStrategy,
            symbols=["AAA", "BBB"],
            ohclv_data=ohclv_data,
            sim_config=sim_config,
            indicator_data=indicator_data,
        )

        # ...but is now flagged as a crash-fallback, not a legitimate zero-trade
        # decision, and names which symbol/error caused it.
        assert result.diagnostics.get("crash_fallback") is True
        assert "AAA" in result.diagnostics.get("strategy_crashed_symbols", {})
        assert "BBB" not in result.diagnostics.get("strategy_crashed_symbols", {})
        assert "rsi_14" in result.diagnostics["strategy_crashed_symbols"]["AAA"]

    def test_legitimate_zero_trades_has_no_crash_diagnostics(self, sim_config):
        """A strategy that runs cleanly and just returns all-zero weights must
        NOT be flagged as a crash -- the two cases must stay distinguishable
        in both directions."""

        class _AlwaysFlatStrategy(BaseStrategy):
            def generate_weights(self, data: pd.DataFrame) -> pd.Series:
                return pd.Series(0.0, index=data.index)

        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        closes = 100.0 + np.arange(len(dates), dtype=float)
        ohclv_data = {"AAA": _make_ohlcv(dates, closes)}

        result = simulate_custom(
            strategy_class=_AlwaysFlatStrategy,
            symbols=["AAA"],
            ohclv_data=ohclv_data,
            sim_config=sim_config,
        )

        assert len(result.trades) == 0
        assert not result.diagnostics.get("crash_fallback")


class TestPerfectForesightCannotProfit:
    def test_perfect_foresight_strategy_loses_money_once_execution_is_delayed(self):
        # Hand-verified price path: up, down, up, flat. A same-bar-execution engine
        # would let this strategy buy right before every up day and sit out every
        # down day — a huge, obviously-impossible edge. With correct T+1 delay, the
        # strategy instead buys the moment each up-move has already happened (at the
        # new high) and sells the moment each down-move has already happened (at the
        # new low) — textbook buy-high-sell-low, which loses money.
        dates = pd.date_range("2023-01-02", periods=5, freq="B")
        closes = np.array([100.0, 110.0, 90.0, 130.0, 130.0])
        ohclv_data = {"X": _make_ohlcv(dates, closes)}
        config = SimulationConfig(
            strategy_name="cheat_test",
            start_date=str(dates[0].date()),
            end_date=str(dates[-1].date()),
            initial_capital=1_000_000.0,
            transaction_cost_pct=0.0,
            slippage_pct=0.0,
            slippage_model="flat",
            allow_short=False,
            deviation_threshold=0.0,
        )

        result = simulate_custom(
            strategy_class=_CheatingPerfectForesightStrategy,
            symbols=["X"],
            ohclv_data=ohclv_data,
            sim_config=config,
        )

        # Buy-and-hold over the same period would be +30% (100 -> 130). A strategy
        # with genuine perfect foresight would do dramatically better than that. This
        # one loses money — proof the "foresight" bought it nothing once T+1 delay
        # is enforced.
        assert result.metrics["total_return"] == pytest.approx(-2 / 11, abs=1e-6)
        assert result.metrics["total_return"] < 0.0
