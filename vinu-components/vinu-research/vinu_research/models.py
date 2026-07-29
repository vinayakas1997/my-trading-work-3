from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from vinu_research.portfolio import PortfolioAnalysisResult


class HypothesisStatus(Enum):
    exploring = "exploring"
    testing = "testing"
    validated = "validated"
    rejected = "rejected"
    monitoring = "monitoring"
    mc_gate_failed = "mc_gate_failed"


@dataclass
class Evidence:
    run_id: int
    iteration: int
    metric: str
    value: float
    conclusion: str
    reasoning: str
    timestamp: str = ""
    metrics_snapshot: dict[str, float] | None = None
    report_path: str | None = None


@dataclass
class Hypothesis:
    hypothesis_id: str
    title: str
    thesis: str
    status: HypothesisStatus = HypothesisStatus.exploring
    universe: list[str] = field(default_factory=list)
    signal_definition: str = ""
    run_cards: list[str] = field(default_factory=list)
    strategy_type: str = ""
    indicators_used: list[str] = field(default_factory=list)
    params_tested: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    invalidation_reason: str | None = None
    best_sharpe: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(cls, title: str, thesis: str, universe: list[str] | None = None) -> Hypothesis:
        import hashlib
        now = datetime.now(timezone.utc).isoformat()
        raw = f"{title}:{thesis}:{now}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return cls(
            hypothesis_id=f"hyp_{h}",
            title=title,
            thesis=thesis,
            universe=universe or [],
            created_at=now,
            updated_at=now,
        )


@dataclass
class Goal:
    goal_id: str
    hypothesis_id: str
    objective: str
    criteria: list[str] = field(default_factory=list)
    status: str = "pending"
    llm_calls_budget: int = 0
    llm_calls_used: int = 0
    time_budget_seconds: float = 0.0
    time_used_seconds: float = 0.0


class ArtifactStatus(Enum):
    CREATED = "CREATED"
    BENCHING = "BENCHING"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    DECAYED = "DECAYED"
    DISABLED = "DISABLED"


@dataclass
class Artifact:
    artifact_id: str
    type: str
    name: str
    universe: list[str]
    status: ArtifactStatus = ArtifactStatus.CREATED
    decay_horizon: int = 60
    signal_definition: str = ""
    entry_rules: str = ""
    exit_rules: str = ""
    created_at: str = ""
    updated_at: str = ""
    # Populated when the artifact originates from an approved vinu-research run
    # (type == "strategy") — the executable code and the run it came from, so a
    # strategy can be re-backtested later without re-running the research loop.
    strategy_code: str = ""
    source_run_id: int | None = None
    initial_sharpe: float = 0.0
    initial_max_dd: float = 0.0
    # Probability initial_sharpe reflects genuine skill after correcting for the
    # cumulative number of research trials run against this symbol (deflated
    # Sharpe ratio, Bailey & Lopez de Prado 2014) — not just this run's trials.
    deflated_sharpe: float = 0.0
    # None when the date range was too short to carve a holdout at all;
    # True/False otherwise, from HoldoutResult.passed.
    holdout_passed: bool | None = None
    # None when no stress window had usable price data, from StressTestResult.passed.
    stress_test_passed: bool | None = None
    # Periodic re-validation tracking — updated when the artifact's strategy is
    # re-backtested against fresh data to check for decay.
    last_validated_ts: str = ""
    revalidation_count: int = 0
    last_revalidation_verdict: bool | None = None
    # Phase 4 — frozen trade-plan JSON for type="trade_plan" artifacts
    trade_plan_data: str = ""

    @classmethod
    def create(cls, type_: str, name: str, universe: list[str] | None = None) -> Artifact:
        import hashlib
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        raw = f"{type_}:{name}:{now}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return cls(
            artifact_id=f"art_{h}",
            type=type_,
            name=name,
            universe=universe or [],
            created_at=now,
            updated_at=now,
        )


# ---------------------------------------------------------------------------
# Phase 4 — Forecast & Trade-Plan models
# ---------------------------------------------------------------------------


@dataclass
class RiskBand:
    max_position_size_pct: float = 0.0
    max_portfolio_risk_pct: float = 0.0
    var_95_limit: float = 0.0
    max_leverage: float = 1.0
    max_cluster_exposure_pct: float = 0.0
    volatility_band_upper: float = 0.0
    volatility_band_lower: float = 0.0


# Comparison operators a deterministic evaluator (Phase 6) can apply to a live
# metric value without interpreting free text.
_VALID_OPERATORS = (">=", "<=", ">", "<", "==", "!=")


@dataclass
class ContingencyRule:
    """A mechanically evaluable in-trade rule: `metric operator threshold -> action`.

    `metric` names a value Phase 6 reads from live state (e.g. "drawdown_pct",
    "realized_vol_ratio", "shock_cluster_correlation"). `condition` is a
    derived human-readable label, not a parsed instruction — evaluation must
    use `metric`/`operator`/`threshold` directly.
    """
    metric: str
    operator: str
    threshold: float
    action: str
    action_params: dict[str, Any] = field(default_factory=dict)
    condition: str = ""

    def __post_init__(self) -> None:
        if self.operator not in _VALID_OPERATORS:
            raise ValueError(f"invalid operator {self.operator!r}, must be one of {_VALID_OPERATORS}")
        if not self.condition:
            self.condition = f"{self.metric} {self.operator} {self.threshold}"


@dataclass
class InvalidationCondition:
    """A mechanically evaluable exit-trigger rule: `metric operator threshold -> action`."""
    metric: str
    operator: str
    threshold: float
    action: str
    action_params: dict[str, Any] = field(default_factory=dict)
    condition: str = ""

    def __post_init__(self) -> None:
        if self.operator not in _VALID_OPERATORS:
            raise ValueError(f"invalid operator {self.operator!r}, must be one of {_VALID_OPERATORS}")
        if not self.condition:
            self.condition = f"{self.metric} {self.operator} {self.threshold}"


@dataclass
class Forecast:
    direction: str
    confidence: float = 0.0
    magnitude_pct: float = 0.0
    magnitude_std: float = 0.0
    horizon_days: int = 0
    brier_score: float = 0.0
    reasoning: str = ""


@dataclass
class TradePlan:
    symbol: str
    timeframe: str
    direction: str
    position_size_pct: float = 0.0
    risk_bands: RiskBand = field(default_factory=RiskBand)
    tranches: list[dict[str, float]] = field(default_factory=list)
    contingency_rules: list[ContingencyRule] = field(default_factory=list)
    invalidation_conditions: list[InvalidationCondition] = field(default_factory=list)
    forecast: Forecast | None = None
    entry_checklist: list[dict[str, str]] = field(default_factory=list)
    exit_checklist: list[dict[str, str]] = field(default_factory=list)
    created_at: str = ""
    version: int = 1

    def to_json(self) -> str:
        return json.dumps(self, default=_dataclass_to_dict, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> TradePlan:
        d = json.loads(raw)
        d["risk_bands"] = RiskBand(**d.get("risk_bands") or {})
        d["contingency_rules"] = [
            ContingencyRule(**r) for r in d.get("contingency_rules") or []
        ]
        d["invalidation_conditions"] = [
            InvalidationCondition(**i) for i in d.get("invalidation_conditions") or []
        ]
        forecast = d.get("forecast")
        d["forecast"] = Forecast(**forecast) if forecast else None
        return cls(**d)


def _dataclass_to_dict(o: Any) -> dict[str, Any]:
    if hasattr(o, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(v) for k, v in o.__dict__.items()}
    if isinstance(o, list):
        return [_dataclass_to_dict(i) for i in o]
    return o


# ---------------------------------------------------------------------------
# Phase 4 — Calibration tracking
# ---------------------------------------------------------------------------


@dataclass
class CalibrationEntry:
    artifact_id: str
    forecast_direction: str
    actual_return_pct: float
    forecast_magnitude_pct: float = 0.0
    brier_score: float = 0.0
    directional_correct: bool = False
    magnitude_error: float = 0.0
    timestamp: str = ""


@dataclass
class CalibrationResult:
    artifact_id: str
    n_entries: int = 0
    accuracy: float = 0.0
    brier_mean: float = 0.0
    magnitude_mape: float = 0.0
    passed: bool = False
    reasons: list[str] = field(default_factory=list)
    timestamp: str = ""


# ---------------------------------------------------------------------------


@dataclass
class BenchEntry:
    artifact_id: str
    date: str
    ic: float = 0.0
    ir: float = 0.0
    ic_positive: bool = False
    sharpe: float = 0.0


@dataclass
class DecaySnapshot:
    artifact_id: str
    evaluation: str
    ic_ratio: float = 0.0
    rolling_ir: float = 0.0
    ic_positive_ratio: float = 0.0
    rolling_sharpe: float = 0.0
    n_entries: int = 0
    timestamp: str = ""


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
    reasoning: str = ""


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
class StressWindowResult:
    name: str
    from_date: str
    to_date: str
    max_drawdown: float | None = None
    total_return: float | None = None
    trade_count: int = 0
    passed: bool | None = None
    note: str = ""


@dataclass
class StressTestResult:
    """
    Replays the winning strategy's actual code through fixed historical crisis
    windows (e.g. the 2020-03 COVID crash) it was never tuned or refined
    against, unlike WalkForwardResult/HoldoutResult whose windows are carved
    from the researched range itself. Answers "what does this do in a shock,"
    not "does its historical edge hold up statistically."
    """
    windows: list[StressWindowResult] = field(default_factory=list)

    @property
    def passed(self) -> bool | None:
        """None if no window could be evaluated (e.g. no price data for the
        period); otherwise True only if every evaluated window passed."""
        evaluated = [w for w in self.windows if w.passed is not None]
        if not evaluated:
            return None
        return all(w.passed for w in evaluated)


@dataclass
class DecisionRecord:
    iteration: int
    hypothesis: str
    approach_chosen: str
    alternatives_considered: list[str]
    reasoning: str
    expected_outcome: str
    actual_result: BacktestResult | None = None
    diagnosis: str | None = None


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
    portfolio: PortfolioAnalysisResult | None = None
    stress_test: StressTestResult | None = None
    pbo: dict[str, float] | None = None
