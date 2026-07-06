from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.models.simulation import SimulationConfig


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", "2023-03-31", freq="D")
    np.random.seed(42)
    n = len(dates)
    aapl = 100.0 * np.exp(np.random.randn(n).cumsum() * 0.01)
    msft = 200.0 * np.exp(np.random.randn(n).cumsum() * 0.01)
    spy = 400.0 * np.exp(np.random.randn(n).cumsum() * 0.008)
    return pd.DataFrame({"AAPL": aapl, "MSFT": msft, "SPY": spy}, index=dates)


@pytest.fixture
def synthetic_weights() -> pd.DataFrame:
    dates = pd.date_range("2023-01-05", "2023-03-30", freq="W")
    np.random.seed(99)
    rows = []
    for d in dates:
        w = np.random.dirichlet(np.ones(3))
        rows.append({"date": d, "AAPL": w[0], "MSFT": w[1], "SPY": w[2]})
    df = pd.DataFrame(rows)
    return df.set_index("date")


@pytest.fixture
def sim_config() -> SimulationConfig:
    return SimulationConfig(
        strategy_name="test_strategy",
        start_date="2023-01-01",
        end_date="2023-03-31",
        initial_capital=1_000_000.0,
        transaction_cost_pct=0.001,
        slippage_pct=0.0005,
        benchmark_tickers=("SPY",),
        allow_short=True,
        deviation_threshold=0.01,
    )


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "simulator_data"
