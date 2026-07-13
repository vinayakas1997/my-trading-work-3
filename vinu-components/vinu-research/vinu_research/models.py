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
