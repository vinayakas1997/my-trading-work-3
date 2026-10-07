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
    # Which trading sessions the bars cover ("regular", "extended", "all" or a comma list; vinu_infra.sessions). Decides the
    # annualisation factor of the metrics; the price service already returned only these sessions' bars.
    sessions: str = "regular"

    # "fixed" = today's behavior (strategy's own weights used as-is). "vol_target"
    # scales exposure to hold realized volatility roughly constant. "kelly" scales
    # exposure from a trailing win-rate/payoff-ratio estimate at a fractional Kelly.
    position_sizing_model: str = "fixed"
    target_annual_vol: float = 0.15
    vol_lookback_days: int = 20
    kelly_fraction: float = 0.25
    kelly_lookback_days: int = 60
    max_leverage: float = 1.0

    # "evidence_confidence" (item #4/#10, system-wide-audit-and-design/
    # 02-open-questions-strategy-and-simulation.md): scales each symbol's
    # weight by Track 2's evidence-confidence for `evidence_must_condition`
    # at that point in the backtest, via SimulationInput.evidence_triggers
    # (pre-fetched by the caller -- this engine makes no network calls of
    # its own). `evidence_must_condition` is recorded here for provenance
    # only; the sizer itself trusts whatever's already in
    # `evidence_triggers`, since the caller is the one that knows how to
    # fetch and filter it (a SQL query in vinu-research, today; over HTTP
    # for any other caller later).
    evidence_must_condition: str | None = None
    evidence_min_confidence_scale: float = 0.5
    evidence_min_sample_size: int = 5

    # "regime_aware" (item #14A factor #2): scales the whole portfolio by
    # a single factor looked up from the current bar's regime
    # (`engine.regime.classify_regime`, already point-in-time safe).
    # `None` uses `sizing.DEFAULT_REGIME_SCALE_MAP`.
    regime_scale_map: dict[str, float] | None = None
    regime_default_scale: float = 1.0

    # "drawdown_aware" (item #14A factor #3): reuses the exact ok/halve/
    # flat/halt threshold ladder `vinu_portfolio.circuit_breakers
    # .PortfolioDrawdownMonitor` uses live (via `compute_drawdown_action`,
    # its pure, HTTP-free core), so backtest sizing and live risk
    # management can never silently drift into two different drawdown
    # policies. Defaults mirror that monitor's own defaults exactly.
    drawdown_threshold: float = -0.20
    drawdown_halve_threshold: float = -0.10
    drawdown_flat_threshold: float = -0.15
    drawdown_abs_loss_threshold: float = 0.0
    drawdown_action_scale_map: dict[str, float] | None = None

    # Caps a single day's order for one symbol at this fraction of that day's
    # traded volume — independent of the Almgren-Chriss cost model, which
    # prices market impact but never refuses to fill an order regardless of
    # size. 1.0 (default) preserves prior behavior (no cap). A strategy that
    # only clears its backtest Sharpe by assuming it can trade an unrealistic
    # fraction of ADV will show it here as unfilled/reduced size, not silently
    # in the cost alone.
    max_pct_of_volume: float = 1.0

    # Stage A (A30): probability that any single symbol's rebalance fill is
    # rejected outright on a given bar (broker-unreliability / partial-outage
    # simulation, VectorBT's `order.reject_prob`). The unfilled delta is
    # retried on the next rebalance, exactly as a real dropped order would be.
    # 0.0 (default) preserves prior behavior. `random_seed` makes a run with
    # a non-zero reject probability fully reproducible — the engine is
    # otherwise deterministic, so this is the only source of randomness.
    execution_reject_prob: float = 0.0
    random_seed: int = 0

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
    # Stage A (A28): True when this fill's size was clipped by
    # `max_pct_of_volume` — i.e. the strategy wanted to trade more of this
    # name on this bar than the ADV cap allows. Previously the clip was
    # silent (only visible as a lower realized return); now a consumer can
    # see directly how volume-constrained a backtest was.
    volume_capped: bool = False


@dataclass
class SimulationInput:
    strategy_name: str
    weight_signals: pd.DataFrame
    price_data: pd.DataFrame
    config: SimulationConfig
    volume_data: pd.DataFrame | None = None
    # item #4/#10: symbol -> that symbol's already-resolved Track 2
    # triggers for config.evidence_must_condition (each a dict with at
    # least trigger_time/outcome_recorded_at/return_at_horizon), only read
    # when config.position_sizing_model == "evidence_confidence". Pre-
    # fetched by the caller, not by this engine -- see
    # EvidenceConfidenceSizer's own docstring for why.
    evidence_triggers: dict[str, list[dict[str, Any]]] | None = None


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
    validation: dict[str, Any] | None = None
    # Populated by simulate_custom() when a strategy's generate_weights() crashed
    # for one or more symbols and was silently replaced with an all-zero weight
    # series (see custom_sim.py). Lets a caller (e.g. vinu-research's
    # _diagnose_failure) tell "strategy crashed" apart from "strategy legitimately
    # traded zero times" instead of both landing on trade_count == 0.
    diagnostics: dict[str, Any] = field(default_factory=dict)
