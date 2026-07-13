from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class SimulationConfig:
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float = 1_000_000.0
    transaction_cost_pct: float = 0.001
    slippage_pct: float = 0.0005
    # Volume-aware market-impact model is the default; flat-percentage costs
    # systematically understate cost on illiquid names and must be opted into.
    slippage_model: str = "almgren_chriss"
    # Explicit — 0.0 is a simplification callers can override, not an assumption
    # baked silently into every Sharpe/Sortino calculation.
    risk_free_rate_annual: float = 0.0
    benchmark_tickers: tuple[str, ...] = ("SPY", "QQQ")
    allow_short: bool = True
    deviation_threshold: float = 0.05


@dataclass
class TradeRecord:
    date: datetime
    symbol: str
    side: str
    shares: float
    price: float
    cost: float
    weight_before: float
    weight_after: float


@dataclass
class SimulationInput:
    strategy_name: str
    weight_signals: pd.DataFrame
    price_data: pd.DataFrame
    config: SimulationConfig
    volume_data: pd.DataFrame | None = None


@dataclass
class SimulationResult:
    strategy_name: str
    run_id: str
    timestamp: datetime
    config: SimulationConfig
    portfolio_values: pd.Series
    daily_returns: pd.Series
    weights_history: pd.DataFrame
    trades: list[TradeRecord]
    metrics: dict[str, float]
    benchmark_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
