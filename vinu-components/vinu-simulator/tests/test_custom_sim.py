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
