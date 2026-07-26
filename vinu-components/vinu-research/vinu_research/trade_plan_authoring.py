"""Phase 4 orchestration: forecast + risk state + personality context -> frozen TradePlan.

This is the only place the LLM forecast (vinu_research.forecast_skill) is combined with
Phase 1's deterministic risk math (vinu_tools.compute.risk) and Phase 2's personality/
shock-clustering angles (vinu-initial-analysis, read via ResearchTools) into a single,
machine-evaluable TradePlan. Consumers (e.g. vinu-agent's TradePlanTool) only ever read the
frozen artifact produced here over HTTP (see server/routes_trade_plan.py) -- they never call
the LLM themselves, keeping Rule 10 ("no LLM outside vinu-research") intact.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from vinu_tools.compute.risk import (
    expected_move_from_vol,
    garch_volatility,
    historical_cvar,
    historical_var,
    kelly_optimal_fraction,
)

from vinu_research.calibration import CalibrationGate, CalibrationTracker
from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import ForecastSkillConfig, generate_forecast
from vinu_research.models import (
    Artifact,
    ArtifactStatus,
    CalibrationEntry,
    ContingencyRule,
    Forecast,
    InvalidationCondition,
    RiskBand,
    TradePlan,
)
from vinu_research.storage.strategy_store import SqliteStrategyStore
from vinu_research.tools import ResearchTools

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS = 252
_MIN_OBSERVATIONS = 20


class TradePlanApprovalError(Exception):
    """Raised when a frozen trade plan fails its approval gate or is already frozen."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons) or "trade plan approval rejected")


async def fetch_risk_state(
    tools: ResearchTools,
    symbol: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Phase 1 risk state for `symbol`: conditional vol, VaR/CVaR, expected move, Kelly fraction.

    Reuses `ResearchTools.get_benchmark_data`, which already fetches candles from
    vinu-stock-price and reduces them to a daily-returns series.
    """
    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=lookback_days)
    returns_series = await tools.get_benchmark_data(symbol, str(from_date), str(to_date))
    if returns_series is None or len(returns_series) < _MIN_OBSERVATIONS:
        return {"status": "insufficient_data"}

    returns = returns_series.values.astype(float)

    vol_path, alpha, beta, omega = garch_volatility(returns, fit=True, time_format="1D")
    valid_vol = vol_path[~np.isnan(vol_path)]
    annualized_volatility = (
        float(valid_vol[-1]) if len(valid_vol) > 0 else float(np.std(returns) * np.sqrt(252))
    )
    daily_volatility = annualized_volatility / np.sqrt(252)

    var_95 = historical_var(returns, confidence_level=0.95)
    cvar_95 = historical_cvar(returns, confidence_level=0.95)
    expected_move_1d_pct = expected_move_from_vol(daily_volatility, confidence=0.68)

    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = float(len(wins) / len(returns)) if len(returns) else 0.0
    avg_win = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss = float(abs(np.mean(losses))) if len(losses) else 0.0
    kelly_fraction = kelly_optimal_fraction(win_rate, avg_win, avg_loss) if avg_loss > 0 else 0.0

    return {
        "status": "ok",
        "annualized_volatility": annualized_volatility,
        "daily_volatility": daily_volatility,
        "garch_alpha": float(alpha),
        "garch_beta": float(beta),
        "garch_persistence": float(alpha + beta),
        "var_95_daily": var_95,
        "cvar_95_daily": cvar_95,
        "expected_move_1d_pct": expected_move_1d_pct,
        "win_rate": win_rate,
        "kelly_fraction": kelly_fraction,
        "n_observations": int(len(returns)),
    }


async def fetch_personality_features(tools: ResearchTools, symbol: str) -> dict[str, Any]:
    """Phase 2 personality/shock-clustering context for `symbol` (latest row of each angle)."""
    personality_rows, cluster_rows = await asyncio.gather(
        tools.get_angle_rows("shock_personality", symbol),
        tools.get_angle_rows("shock_clustering", symbol),
    )
    return {
        "shock_personality": personality_rows[-1] if personality_rows else {},
        "shock_clustering": cluster_rows[-1] if cluster_rows else {},
    }


def _build_risk_band(risk_state: dict[str, Any], personality: dict[str, Any]) -> RiskBand:
    if risk_state.get("status") != "ok":
        return RiskBand()

    vol = risk_state["annualized_volatility"]
    var_95 = abs(risk_state["var_95_daily"])
    kelly = risk_state["kelly_fraction"]

    # Half-Kelly, capped at 10% of portfolio per position -- avoids full-Kelly's
    # well-known overbetting under estimation error.
    max_position_size_pct = min(max(kelly * 0.5, 0.0), 0.10)
    max_portfolio_risk_pct = min(var_95 * 2, 0.05)

    cluster_members = (personality.get("shock_clustering") or {}).get("cluster_members") or []
    max_cluster_exposure_pct = 0.15 if cluster_members else 0.25

    return RiskBand(
        max_position_size_pct=max_position_size_pct,
        max_portfolio_risk_pct=max_portfolio_risk_pct,
        var_95_limit=var_95,
        max_leverage=1.0,
        max_cluster_exposure_pct=max_cluster_exposure_pct,
        volatility_band_upper=vol * 1.5,
        volatility_band_lower=vol * 0.5,
    )


def _build_contingency_rules(
    risk_state: dict[str, Any],
    personality: dict[str, Any],
) -> list[ContingencyRule]:
    rules = [
        ContingencyRule(
            metric="drawdown_pct",
            operator=">=",
            threshold=0.05,
            action="reduce_position",
            action_params={"reduce_by_pct": 0.5},
        ),
    ]

    if risk_state.get("status") == "ok":
        # realized_vol_ratio = live realized vol / this plan's GARCH-forecast vol at
        # freeze time -- a live-vs-forecast divergence, not a re-derivation of GARCH.
        rules.append(
            ContingencyRule(
                metric="realized_vol_ratio",
                operator=">=",
                threshold=1.5,
                action="tighten_stop",
                action_params={"tighten_by_pct": 0.3},
            )
        )

    cluster_members = (personality.get("shock_clustering") or {}).get("cluster_members") or []
    if cluster_members:
        rules.append(
            ContingencyRule(
                metric="shock_cluster_correlation",
                operator=">=",
                threshold=0.7,
                action="reduce_position",
                action_params={"reduce_by_pct": 0.3},
            )
        )

    return rules


def _build_invalidation_conditions(
    risk_state: dict[str, Any],
    forecast: Forecast,
) -> list[InvalidationCondition]:
    conditions = [
        InvalidationCondition(
            metric="gap_against_position_pct",
            operator=">=",
            threshold=0.02,
            action="exit",
        ),
        InvalidationCondition(
            metric="unrealized_pnl_pct",
            operator="<=",
            threshold=-0.08,
            action="exit",
        ),
    ]

    if forecast.magnitude_std > 0:
        conditions.append(
            InvalidationCondition(
                metric="realized_move_vs_forecast_std",
                operator=">=",
                threshold=2.0,
                action="exit",
            )
        )

    return conditions


async def author_trade_plan(
    symbol: str,
    timeframe: str,
    config: ResearchConfig,
    tools: ResearchTools,
    llm_client: Any | None = None,
) -> TradePlan:
    """Author a complete TradePlan: forecast, sizing, risk bands, contingency + invalidation rules.

    Every contingency/invalidation rule is a metric/operator/threshold triple (see
    ContingencyRule/InvalidationCondition in models.py) so Phase 6 can evaluate it against
    live data without interpreting free text -- this is the completeness bar plan.md's
    "Warning for whoever implements Phase 4" requires.
    """
    symbol = symbol.upper()
    risk_state, personality = await asyncio.gather(
        fetch_risk_state(tools, symbol),
        fetch_personality_features(tools, symbol),
    )

    forecast = await generate_forecast(symbol, personality, risk_state, config, llm_client)

    risk_bands = _build_risk_band(risk_state, personality)
    contingency_rules = _build_contingency_rules(risk_state, personality)
    invalidation_conditions = _build_invalidation_conditions(risk_state, forecast)

    return TradePlan(
        symbol=symbol,
        timeframe=timeframe,
        direction=forecast.direction,
        position_size_pct=risk_bands.max_position_size_pct,
        risk_bands=risk_bands,
        contingency_rules=contingency_rules,
        invalidation_conditions=invalidation_conditions,
        forecast=forecast,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def freeze_trade_plan(store: SqliteStrategyStore, plan: TradePlan) -> Artifact:
    """Persist `plan` as a new CREATED Artifact(type="trade_plan"). Not yet tradeable."""
    artifact = Artifact.create(
        type_="trade_plan",
        name=f"trade_plan_{plan.symbol}_{plan.timeframe}",
        universe=[plan.symbol],
    )
    artifact.trade_plan_data = plan.to_json()
    return store.upsert_artifact(artifact)


def approve_trade_plan(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
) -> Artifact:
    """Promote a frozen trade plan to ACTIVE, gated by CalibrationGate (fail-closed).

    The calibration tracker is always rebuilt from persisted entries (`load_calibration_tracker`)
    -- never a fresh empty one -- so approval reflects Phase 7's real realized-outcome history,
    not whatever the caller happened to construct.

    Once ACTIVE, a trade plan is immutable -- a revision requires authoring and freezing a
    new artifact, not mutating this one.
    """
    artifact = store.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"no artifact with id {artifact_id}")
    if artifact.type != "trade_plan":
        raise ValueError(f"artifact {artifact_id} is not a trade_plan (type={artifact.type})")
    if artifact.status == ArtifactStatus.ACTIVE:
        raise TradePlanApprovalError(
            ["trade plan is already frozen ACTIVE; revisions require authoring a new version"]
        )

    tracker = load_calibration_tracker(store, artifact_id, config)
    gate = CalibrationGate(tracker, min_window=tracker.config.min_calibration_window)
    result = gate.check()
    if not result.passed:
        raise TradePlanApprovalError(result.reasons)

    artifact.status = ArtifactStatus.ACTIVE
    return store.upsert_artifact(artifact)


def record_realized_outcome(
    store: SqliteStrategyStore,
    artifact_id: str,
    actual_return_pct: float,
    config: ForecastSkillConfig | None = None,
) -> CalibrationEntry:
    """Score a closed trade-plan position's realized return against its frozen forecast and
    persist the result -- Phase 7's write path into Phase 4's calibration gate. Reuses
    `CalibrationTracker.add_entry`'s scoring exactly rather than recomputing Brier/directional/
    magnitude-error inline here.
    """
    artifact = store.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"no artifact with id {artifact_id}")
    if not artifact.trade_plan_data:
        raise ValueError(f"artifact {artifact_id} has no trade_plan_data")

    plan = TradePlan.from_json(artifact.trade_plan_data)
    if plan.forecast is None:
        raise ValueError(f"trade plan for {artifact_id} has no forecast to score")

    tracker = CalibrationTracker(artifact_id, config)
    entry = tracker.add_entry(plan.forecast, actual_return_pct)
    return store.append_calibration_entry(entry)


def load_calibration_tracker(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
) -> CalibrationTracker:
    """Reconstruct a CalibrationTracker from persisted `calibration_entries` rows."""
    tracker = CalibrationTracker(artifact_id, config)
    tracker.load_entries(store.get_calibration_entries(artifact_id))
    return tracker
