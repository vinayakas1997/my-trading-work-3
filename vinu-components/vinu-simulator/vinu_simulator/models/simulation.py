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
    # Bar granularity of price_data/weight_signals — drives annualization
    # (periods-per-year) in metrics.py. "1d" preserves prior behavior.
    interval: str = "1d"

    # "fixed" = today's behavior (strategy's own weights used as-is). "vol_target"
    # scales exposure to hold realized volatility roughly constant. "kelly" scales
    # exposure from a trailing win-rate/payoff-ratio estimate at a fractional Kelly.
    position_sizing_model: str = "fixed"
    target_annual_vol: float = 0.15
    vol_lookback_days: int = 20
    kelly_fraction: float = 0.25
    kelly_lookback_days: int = 60
    max_leverage: float = 1.0

    # Caps a single day's order for one symbol at this fraction of that day's
    # traded volume — independent of the Almgren-Chriss cost model, which
    # prices market impact but never refuses to fill an order regardless of
    # size. 1.0 (default) preserves prior behavior (no cap). A strategy that
    # only clears its backtest Sharpe by assuming it can trade an unrealistic
    # fraction of ADV will show it here as unfilled/reduced size, not silently
    # in the cost alone.
    max_pct_of_volume: float = 1.0

    # Compute extended metrics (VaR, CVaR, drawdown duration, win/loss ratios,
    # benchmark metrics, Sharpe CI, turnover). When False, only basic metrics
    # (total_return, cagr, sharpe, sortino, max_drawdown, calmar, win_rate,
    # skewness, kurtosis, annual_volatility) are returned.
    full_metrics: bool = True


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
