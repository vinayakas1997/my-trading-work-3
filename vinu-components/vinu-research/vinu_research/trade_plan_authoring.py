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
    AngleCalibrationEntry,
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
        float(valid_vol[-1]) if len(valid_vol) > 0 else float(np.std(returns, ddof=1) * np.sqrt(252))
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
    # how-to-make-it-live.md #17: carry CVaR + daily vol onto the frozen plan so
    # the live entry path can gate/scale on them. Stored as positive fractions.
    cvar_95 = abs(float(risk_state.get("cvar_95_daily", 0.0) or 0.0))
    daily_vol = abs(float(risk_state.get("daily_volatility", 0.0) or 0.0))

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
        cvar_95_limit=cvar_95,
        daily_vol=daily_vol,
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

    if forecast.horizon_days > 0:
        conditions.extend([
            InvalidationCondition(
                metric="probability_of_failure",
                operator=">=",
                threshold=0.3,
                action="trim",
                action_params={"reduce_by_pct": 0.5},
                condition="P_failure >= 0.3",
            ),
            InvalidationCondition(
                metric="probability_of_failure",
                operator=">=",
                threshold=0.6,
                action="exit",
                action_params={"reason": "high_probability_failure"},
                condition="P_failure >= 0.6",
            ),
        ])

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
    logger.info("[%s %s] Authoring trade plan: fetching risk state + personality context", symbol, timeframe)
    risk_state, personality = await asyncio.gather(
        fetch_risk_state(tools, symbol),
        fetch_personality_features(tools, symbol),
    )
    logger.info("[%s %s] Risk state status=%s", symbol, timeframe, risk_state.get("status"))

    forecast = await generate_forecast(symbol, personality, risk_state, config, llm_client)
    logger.info(
        "[%s %s] Forecast: direction=%s magnitude_std=%.4f",
        symbol, timeframe, forecast.direction, forecast.magnitude_std,
    )

    risk_bands = _build_risk_band(risk_state, personality)
    contingency_rules = _build_contingency_rules(risk_state, personality)
    invalidation_conditions = _build_invalidation_conditions(risk_state, forecast)
    logger.info(
        "[%s %s] Trade plan authored: %d contingency rule(s), %d invalidation condition(s)",
        symbol, timeframe, len(contingency_rules), len(invalidation_conditions),
    )

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
    # Stage A (A9 -- daily_stock_analysis's mandatory-invalidation-conditions
    # rule, see other-repos-world/comprison-other-vinu/04-daily_stock_analysis.md):
    # a trade plan with no way to be proven wrong is one vinu-live's
    # orchestrator will hold open indefinitely on the time-stop alone.
    # `_build_invalidation_conditions` currently always returns >= 2 (the
    # first two are unconditional), so this is a belt-and-suspenders guard
    # against a future refactor accidentally making every condition
    # conditional -- fail closed at freeze time, not silently later.
    if not plan.invalidation_conditions:
        raise ValueError(
            f"trade plan for {plan.symbol} has no invalidation conditions -- "
            "refusing to freeze a plan that can never be invalidated"
        )
    artifact = Artifact.create(
        type_="trade_plan",
        name=f"trade_plan_{plan.symbol}_{plan.timeframe}",
        universe=[plan.symbol],
    )
    artifact.trade_plan_data = plan.to_json()
    saved = store.upsert_artifact(artifact)
    logger.info("[%s] Froze trade plan artifact_id=%s (status=%s)", plan.symbol, saved.artifact_id, saved.status)
    return saved


def approve_trade_plan(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
    *,
    force: bool = False,
    approver: str = "",
) -> Artifact:
    """Promote a frozen trade plan to ACTIVE, gated by CalibrationGate (fail-closed).

    The calibration tracker is always rebuilt from persisted entries (`load_calibration_tracker`)
    -- never a fresh empty one -- so approval reflects Phase 7's real realized-outcome history,
    not whatever the caller happened to construct.

    Once ACTIVE, a trade plan is immutable -- a revision requires authoring and freezing a
    new artifact, not mutating this one.

    force=True (Stage 0, G2b, research-discussion-v1/complete-plan/
    01-native-gaps.md): an explicit human override that bypasses whichever
    check would otherwise reject -- mirrors vinu_research.promotion's
    existing `/artifacts/{id}/promote?force=true` pattern, same "human
    accountability, not a silent bypass" posture the user chose for this
    (2026-09-10): `approver` is required whenever force is used and is
    logged with the override, not merged into the ordinary approval log
    line, so a forced approval is always distinguishable from a gate-
    cleared one after the fact.
    """
    if force and not approver:
        raise ValueError("approver is required when force=True")
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

    if not tracker.entries:
        # Stage 0 (G2a bootstrap fix, research-discussion-v1/complete-plan/
        # 01-native-gaps.md): calibration_entries are only ever written by
        # vinu-live's feedback_loop.py after a position closes -- which
        # requires this exact artifact to already be ACTIVE. Checking
        # CalibrationGate on a fresh trade plan (zero entries, always)
        # therefore made approval unsatisfiable for every trade plan ever
        # authored, not just hard to automate -- confirmed 2026-09-10.
        # On a first-ever approval, trust the symbol's own ACTIVE strategy
        # artifact instead: it already cleared vinu_research.promotion.
        # meets_promotion_bar() (deflated Sharpe / holdout / stress / PBO)
        # to get there, which is a real, upstream statistical validation --
        # not a rubber stamp. If the symbol has no ACTIVE strategy backing
        # it at all, still fail closed; there is no statistical basis to
        # approve on.
        symbol = artifact.universe[0] if artifact.universe else ""
        has_active_strategy = any(
            a.type == "strategy"
            for a in store.list_artifacts_for_symbol(symbol, statuses=[ArtifactStatus.ACTIVE])
        )
        if not has_active_strategy:
            reasons = [
                f"no calibration history yet for this trade plan, and no ACTIVE "
                f"strategy artifact for {symbol} to bootstrap approval from"
            ]
            if not force:
                logger.warning("[%s] Approval REJECTED: %s", artifact_id, "; ".join(reasons))
                raise TradePlanApprovalError(reasons)
            logger.warning(
                "[%s] Approval FORCED by %s despite: %s",
                artifact_id, approver, "; ".join(reasons),
            )
        artifact.status = ArtifactStatus.ACTIVE
        saved = store.upsert_artifact(artifact)
        if force:
            logger.info("[%s] Approved (forced by %s) -- trade plan is now ACTIVE", artifact_id, approver)
        else:
            logger.info(
                "[%s] Approved via strategy-bootstrap (no calibration history yet, "
                "%s has an ACTIVE strategy artifact) -- trade plan is now ACTIVE",
                artifact_id, symbol,
            )
        return saved

    gate = CalibrationGate(tracker, min_window=tracker.config.min_calibration_window)
    result = gate.check()
    if not result.passed:
        if not force:
            logger.warning("[%s] Approval REJECTED: %s", artifact_id, "; ".join(result.reasons))
            raise TradePlanApprovalError(result.reasons)
        logger.warning(
            "[%s] Approval FORCED by %s despite: %s",
            artifact_id, approver, "; ".join(result.reasons),
        )

    artifact.status = ArtifactStatus.ACTIVE
    saved = store.upsert_artifact(artifact)
    if force and not result.passed:
        logger.info("[%s] Approved (forced by %s) -- trade plan is now ACTIVE", artifact_id, approver)
    else:
        logger.info("[%s] Approved -- trade plan is now ACTIVE", artifact_id)
    return saved


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

    Also fans the SAME scored outcome out to one AngleCalibrationEntry per
    entry in `artifact.origin_angles` -- the real per-angle calibration
    tracker (previously nonexistent, confirmed by reading this whole
    module and calibration.py directly: nothing anywhere was keyed by
    angle name). Never a second, independently-computed score -- every
    angle attributed to this artifact gets the identical
    directional_correct/brier_score/magnitude_error this one real close
    produced. Empty `origin_angles` (every artifact whose research pass
    didn't report angle usage, or that predates this field) means no
    per-angle entries are written -- silently, not an error, since most
    artifacts genuinely have no attribution data.
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
    saved = store.append_calibration_entry(entry)

    for angle_name in artifact.origin_angles:
        angle_entry = AngleCalibrationEntry(
            angle_name=angle_name,
            artifact_id=artifact_id,
            forecast_direction=entry.forecast_direction,
            actual_return_pct=entry.actual_return_pct,
            forecast_magnitude_pct=entry.forecast_magnitude_pct,
            brier_score=entry.brier_score,
            directional_correct=entry.directional_correct,
            magnitude_error=entry.magnitude_error,
            timestamp=entry.timestamp,
        )
        store.append_angle_calibration_entry(angle_entry)

    logger.info(
        "[%s] Recorded realized outcome: actual_return_pct=%.4f (attributed to %d angle(s))",
        artifact_id, actual_return_pct, len(artifact.origin_angles),
    )
    return saved


def load_calibration_tracker(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
) -> CalibrationTracker:
    """Reconstruct a CalibrationTracker from persisted `calibration_entries` rows."""
    tracker = CalibrationTracker(artifact_id, config)
    tracker.load_entries(store.get_calibration_entries(artifact_id))
    return tracker
