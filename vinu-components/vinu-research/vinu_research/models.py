from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoryBlock:
    ticker: str
    period: dict[str, Any]
    impact_events: list[dict[str, Any]]
    time_gaps: list[dict[str, Any]]
    correlations: dict[str, Any]
    drawdown_events: list[dict[str, Any]]
    baseline: dict[str, Any]


@dataclass
class DrawdownEvent:
    peak_date: str
    trough_date: str
    drop_pct: float
    news_attributed_pct: float
    high_impact_events_in_window: int
    sessions_involved: list[str]


@dataclass
class BacktestMetrics:
    total_return: float = 0.0
    cagr: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    tail_ratio: float = 0.0
    max_dd_duration_days: int = 0
    avg_drawdown: float = 0.0
    recovery_time_days: int = 0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    win_loss_ratio: float = 0.0
    hit_rate: float = 0.0
    annual_turnover: float = 0.0
    sharpe_standard_error: float = 0.0
    sharpe_p_value: float = 1.0
    sharpe_ci_95_low: float = 0.0
    sharpe_ci_95_high: float = 0.0

    beta: float = 0.0
    alpha: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    market_correlation: float = 0.0
    up_capture: float = 0.0
    down_capture: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> BacktestMetrics:
        return cls(**{k: d.get(k, 0.0) for k in cls.__dataclass_fields__})


@dataclass
class BacktestResult:
    run_id: str
    strategy_name: str
    metrics: BacktestMetrics
    benchmark_metrics: dict[str, dict[str, float]]
    trade_count: int
    equity_points: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CriticFeedback:
    verdict: str
    reasoning: str
    suggestions: list[str]


@dataclass
class IterationRecord:
    iteration: int
    strategy_code: str
    result: BacktestResult
    critique: CriticFeedback


@dataclass
class OOSMetrics:
    is_sharpe: float = 0.0
    is_max_dd: float = 0.0
    is_win_rate: float = 0.0
    is_cagr: float = 0.0
    is_total_return: float = 0.0
    oos_sharpe: float = 0.0
    oos_max_dd: float = 0.0
    oos_win_rate: float = 0.0
    oos_cagr: float = 0.0
    oos_total_return: float = 0.0
    sharpe_gap: float = 0.0
    max_dd_gap: float = 0.0
    n_windows: int = 0


@dataclass
class WalkForwardResult:
    windows: list[dict[str, Any]] = field(default_factory=list)
    aggregated_is_metrics: dict[str, float] = field(default_factory=dict)
    aggregated_oos_metrics: dict[str, float] = field(default_factory=dict)
    sharpe_gap: float = 0.0
    max_dd_gap: float = 0.0
    win_rate_gap: float = 0.0
    n_windows: int = 0
    method: str = "expanding"

    @property
    def has_walk_forward(self) -> bool:
        return self.n_windows > 0 and bool(self.aggregated_oos_metrics)


@dataclass
class HoldoutResult:
    """
    Result of re-testing the strategy on a trailing slice of the requested date
    range that the refinement loop never touched — no filter was ever chosen using
    this data. Distinct from WalkForwardResult, whose windows are still cut from
    the same range the loop tuned filters against.
    """
    holdout_from: str
    holdout_to: str
    in_sample_sharpe: float
    holdout_sharpe: float
    holdout_max_drawdown: float
    holdout_total_return: float
    holdout_trade_count: int
    passed: bool
    note: str = ""


@dataclass
class LlmCandidate:
    code: str
    features_required: list[str] = field(default_factory=list)
    reasoning: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    validated: bool = False


@dataclass
class ResearchResult:
    symbol: str
    from_date: str
    to_date: str
    user_idea: str
    iterations: list[IterationRecord]
    best_result: BacktestResult | None
    best_iteration: int
    total_iterations: int
    report_md: str
    walk_forward: WalkForwardResult | None = None
    holdout: HoldoutResult | None = None
