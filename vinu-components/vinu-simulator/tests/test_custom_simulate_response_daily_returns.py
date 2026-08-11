"""Tests for CustomSimulateResponse.daily_returns -- added for
vinu-research's Phase 1 sweep-grid PBO computation, which needs a real
per-period returns series across several candidates (not just summary
metrics). Uses the same engine-level, no-network fixture pattern as
test_custom_sim.py -- exercises the exact construction routes_read.py's
simulate_custom() route performs, without needing a live HTTP server or
external price/features/strategy clients.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.engine.custom_sim import simulate_custom
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.models.simulation import SimulationConfig
from vinu_simulator.server.schemas import CustomSimulateResponse


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


def _build_response(result) -> CustomSimulateResponse:
    """Same construction routes_read.py's simulate_custom() route performs."""
    return CustomSimulateResponse(
        run_id=result.run_id or "test-run",
        strategy_name=result.strategy_name,
        timestamp=result.timestamp,
        metrics=result.metrics,
        benchmark_metrics=result.benchmark_metrics,
        trade_count=len(result.trades),
        equity_points=len(result.portfolio_values),
        validation=result.validation,
        daily_returns=(
            result.daily_returns.fillna(0.0).tolist() if not result.daily_returns.empty else []
        ),
    )


class TestCustomSimulateResponseDailyReturns:
    def test_daily_returns_present_one_shorter_than_equity_points(self, sim_config) -> None:
        """The engine drops the first row's undefined pct_change rather
        than NaN-filling it -- daily_returns is one entry shorter than
        equity_points, not equal to it. Consistent across every candidate
        run over the same date range, which is all PBO's returns_matrix
        actually needs (equal-length columns), not a specific count."""
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        closes = 100.0 + np.arange(len(dates), dtype=float)
        result = simulate_custom(
            strategy_class=_ConstantWeightStrategy,
            symbols=["AAA"],
            ohclv_data={"AAA": _make_ohlcv(dates, closes)},
            sim_config=sim_config,
        )
        response = _build_response(result)
        assert response.equity_points > 0
        assert len(response.daily_returns) == response.equity_points - 1

    def test_daily_returns_has_no_nan_or_inf(self, sim_config) -> None:
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        closes = 100.0 + np.arange(len(dates), dtype=float)
        result = simulate_custom(
            strategy_class=_ConstantWeightStrategy,
            symbols=["AAA"],
            ohclv_data={"AAA": _make_ohlcv(dates, closes)},
            sim_config=sim_config,
        )
        response = _build_response(result)
        assert all(math.isfinite(v) for v in response.daily_returns)

    def test_daily_returns_fillna_guard_handles_a_genuine_mid_series_nan(self, sim_config) -> None:
        """fillna(0.0) is defense-in-depth for a NaN appearing anywhere in
        the series (e.g. a real mid-series data gap), not just the
        already-dropped leading row -- verify it directly rather than only
        via the real engine's current (NaN-free) output."""
        raw = pd.Series([0.01, float("nan"), -0.02, 0.03])
        cleaned = raw.fillna(0.0).tolist()
        assert cleaned == [0.01, 0.0, -0.02, 0.03]
        assert all(math.isfinite(v) for v in cleaned)
