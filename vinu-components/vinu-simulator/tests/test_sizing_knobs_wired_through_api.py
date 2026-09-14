"""Regression for the execution-realism knobs (position_sizing_model,
target_annual_vol, kelly_fraction, max_leverage, max_pct_of_volume,
execution_reject_prob, ...) being implemented and tested inside
WeightSimulator/FractionalKellySizer/VolTargetSizer, but never reachable
through the real HTTP request schemas -- every backtest run through the
actual API (including the one vinu-research's tools.run_backtest calls,
/simulate/custom) always got SimulationConfig's silently-optimistic
defaults (fixed sizing, no ADV cap, zero reject probability) regardless of
what the caller intended. See high-expectations gate-conflict audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.config import VinuSimulatorConfig
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.server.schemas import CustomSimulateRequest, SimulateRequest
from vinu_simulator.service import SimulatorService, _optional_sizing_kwargs


class _ConstantWeightStrategy(BaseStrategy):
    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(0.5, index=data.index)


def _make_ohlcv(dates: pd.DatetimeIndex) -> pd.DataFrame:
    closes = 100.0 + np.arange(len(dates), dtype=float)
    return pd.DataFrame(
        {
            "open": closes, "high": closes * 1.01, "low": closes * 0.99,
            "close": closes, "volume": np.full(len(dates), 1_000_000.0),
        },
        index=dates,
    )


@pytest.fixture
def service(tmp_path) -> SimulatorService:
    config = VinuSimulatorConfig(
        host="127.0.0.1", port=0, data_root=tmp_path,
        initial_capital=1_000_000.0, transaction_cost_pct=0.001, slippage_pct=0.0005,
        benchmark_tickers=("SPY",), allow_short=True,
        strategy_api_url="http://unused", stock_api_url="http://unused",
        features_api_url="http://unused", deviation_threshold=0.05,
    )
    return SimulatorService(config=config)


class TestOptionalSizingKwargs:
    def test_none_fields_are_omitted(self) -> None:
        req = CustomSimulateRequest(strategy_code="x", class_name="X", symbols=["AAPL"])
        assert _optional_sizing_kwargs(req) == {}

    def test_set_fields_are_forwarded(self) -> None:
        req = CustomSimulateRequest(
            strategy_code="x", class_name="X", symbols=["AAPL"],
            max_pct_of_volume=0.1, execution_reject_prob=0.2,
        )
        kwargs = _optional_sizing_kwargs(req)
        assert kwargs == {"max_pct_of_volume": 0.1, "execution_reject_prob": 0.2}


class TestCustomSimulatePlumbsSizingFields:
    def test_defaults_preserve_prior_behavior(self, service, monkeypatch) -> None:
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        ohclv = {"AAPL": _make_ohlcv(dates)}
        monkeypatch.setattr(service, "_get_ohclv_cached", lambda *a, **kw: ohclv)

        captured: dict = {}

        def _fake_run_custom_sim(*, strategy_class, symbols, ohclv_data, sim_config, indicator_data):
            captured["sim_config"] = sim_config
            from vinu_simulator.models.simulation import SimulationResult
            from datetime import datetime, timezone
            import pandas as _pd
            return SimulationResult(
                run_id="r1", strategy_name="X", timestamp=datetime.now(timezone.utc),
                config=sim_config, metrics={}, benchmark_metrics={},
                portfolio_values=_pd.Series(dtype=float), daily_returns=_pd.Series(dtype=float),
                weights_history=_pd.DataFrame(), trades=[],
            )
        monkeypatch.setattr("vinu_simulator.service._run_custom_sim", _fake_run_custom_sim)

        req = CustomSimulateRequest(
            strategy_code="class X(BaseStrategy):\n    def generate_weights(self, data): return data['close']*0",
            class_name="X", symbols=["AAPL"], start_date="2023-01-02", end_date="2023-01-20",
        )
        service._simulate_custom_impl(req)

        cfg = captured["sim_config"]
        assert cfg.position_sizing_model == "fixed"
        assert cfg.max_pct_of_volume == 1.0
        assert cfg.execution_reject_prob == 0.0

    def test_opted_in_fields_reach_simulation_config(self, service, monkeypatch) -> None:
        dates = pd.date_range("2023-01-02", "2023-01-20", freq="B")
        ohclv = {"AAPL": _make_ohlcv(dates)}
        monkeypatch.setattr(service, "_get_ohclv_cached", lambda *a, **kw: ohclv)

        captured: dict = {}

        def _fake_run_custom_sim(*, strategy_class, symbols, ohclv_data, sim_config, indicator_data):
            captured["sim_config"] = sim_config
            from vinu_simulator.models.simulation import SimulationResult
            from datetime import datetime, timezone
            import pandas as _pd
            return SimulationResult(
                run_id="r1", strategy_name="X", timestamp=datetime.now(timezone.utc),
                config=sim_config, metrics={}, benchmark_metrics={},
                portfolio_values=_pd.Series(dtype=float), daily_returns=_pd.Series(dtype=float),
                weights_history=_pd.DataFrame(), trades=[],
            )
        monkeypatch.setattr("vinu_simulator.service._run_custom_sim", _fake_run_custom_sim)

        req = CustomSimulateRequest(
            strategy_code="class X(BaseStrategy):\n    def generate_weights(self, data): return data['close']*0",
            class_name="X", symbols=["AAPL"], start_date="2023-01-02", end_date="2023-01-20",
            position_sizing_model="vol_target", target_annual_vol=0.2, max_pct_of_volume=0.05,
            execution_reject_prob=0.1, random_seed=42,
        )
        service._simulate_custom_impl(req)

        cfg = captured["sim_config"]
        assert cfg.position_sizing_model == "vol_target"
        assert cfg.target_annual_vol == 0.2
        assert cfg.max_pct_of_volume == 0.05
        assert cfg.execution_reject_prob == 0.1
        assert cfg.random_seed == 42

    def test_config_hash_differs_by_sizing_fields(self, service, monkeypatch) -> None:
        """Regression: adding these fields without adding them to the cache
        key would make two requests differing ONLY in e.g.
        execution_reject_prob collide on the same cached result."""
        req_a = CustomSimulateRequest(
            strategy_code="x", class_name="X", symbols=["AAPL"],
            start_date="2023-01-02", end_date="2023-01-20", execution_reject_prob=0.0,
        )
        req_b = CustomSimulateRequest(
            strategy_code="x", class_name="X", symbols=["AAPL"],
            start_date="2023-01-02", end_date="2023-01-20", execution_reject_prob=0.5,
        )
        hash_a = service._compute_config_hash({
            "type": "custom", "strategy_code": req_a.strategy_code, "class_name": req_a.class_name,
            "symbols": sorted(req_a.symbols), "start_date": req_a.start_date, "end_date": req_a.end_date,
            "initial_capital": req_a.initial_capital, "transaction_cost_pct": req_a.transaction_cost_pct,
            "slippage_pct": req_a.slippage_pct, "slippage_model": req_a.slippage_model,
            "benchmark_tickers": None, "allow_short": req_a.allow_short,
            "deviation_threshold": req_a.deviation_threshold, "interval": req_a.interval,
            "indicators": None, "full_metrics": req_a.full_metrics, "run_validation": req_a.run_validation,
            "position_sizing_model": req_a.position_sizing_model, "target_annual_vol": req_a.target_annual_vol,
            "vol_lookback_days": req_a.vol_lookback_days, "kelly_fraction": req_a.kelly_fraction,
            "kelly_lookback_days": req_a.kelly_lookback_days, "max_leverage": req_a.max_leverage,
            "max_pct_of_volume": req_a.max_pct_of_volume, "execution_reject_prob": req_a.execution_reject_prob,
            "random_seed": req_a.random_seed,
        })
        hash_b = service._compute_config_hash({
            "type": "custom", "strategy_code": req_b.strategy_code, "class_name": req_b.class_name,
            "symbols": sorted(req_b.symbols), "start_date": req_b.start_date, "end_date": req_b.end_date,
            "initial_capital": req_b.initial_capital, "transaction_cost_pct": req_b.transaction_cost_pct,
            "slippage_pct": req_b.slippage_pct, "slippage_model": req_b.slippage_model,
            "benchmark_tickers": None, "allow_short": req_b.allow_short,
            "deviation_threshold": req_b.deviation_threshold, "interval": req_b.interval,
            "indicators": None, "full_metrics": req_b.full_metrics, "run_validation": req_b.run_validation,
            "position_sizing_model": req_b.position_sizing_model, "target_annual_vol": req_b.target_annual_vol,
            "vol_lookback_days": req_b.vol_lookback_days, "kelly_fraction": req_b.kelly_fraction,
            "kelly_lookback_days": req_b.kelly_lookback_days, "max_leverage": req_b.max_leverage,
            "max_pct_of_volume": req_b.max_pct_of_volume, "execution_reject_prob": req_b.execution_reject_prob,
            "random_seed": req_b.random_seed,
        })
        assert hash_a != hash_b
