from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.calibration import get_angle_calibration
from vinu_research.decay import approve_decay_action
from vinu_research.forecast_skill import compute_calibration
from vinu_research.service import ResearchService
from vinu_research.storage.strategy_store import InvalidStatusTransition
from vinu_research.tools import ResearchTools
from vinu_research.trade_plan_authoring import (
    TradePlanApprovalError,
    approve_trade_plan,
    author_trade_plan,
    freeze_trade_plan,
    record_realized_outcome,
    update_in_trade_action,
)
from vinu_research.trade_score_calibration import approve_proposal as approve_trade_score_calibration

router = APIRouter()

_service: ResearchService | None = None


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


class GenerateTradePlanRequest(BaseModel):
    timeframe: str = Field(default="daily", pattern=r"^(intraday|daily|swing)$")
    summary_context: dict[str, str | int] | None = Field(
        default=None,
        description="Optional summary from Summary Agent (summary, source_run_id, angles_with_data, angle_count)",
    )


def _forecast_reasoning(trade_plan_data: str | None) -> str:
    """Surfaces the LLM's free-text forecast justification at the top level
    of the API response -- it was already fully persisted inside the
    trade_plan_data JSON blob (forecast.reasoning) but nothing ever read it
    back out, making it effectively unreachable. See the foundation-fixes
    audit in missing-pieces-of-system/narating-agents/."""
    if not trade_plan_data:
        return ""
    try:
        return (json.loads(trade_plan_data).get("forecast") or {}).get("reasoning", "")
    except Exception:
        return ""


def _artifact_to_dict(artifact: Any) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "name": artifact.name,
        "universe": artifact.universe,
        "status": artifact.status.value,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
        "trade_plan_data": artifact.trade_plan_data,
        "reasoning": _forecast_reasoning(artifact.trade_plan_data),
    }


@router.post("/trade-plan/{symbol}")
async def generate_trade_plan(symbol: str, body: GenerateTradePlanRequest) -> dict[str, Any]:
    """Author + freeze a complete trade plan for `symbol` (status stays CREATED)."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    tools = ResearchTools(_service.config)
    try:
        plan = await author_trade_plan(
            symbol,
            body.timeframe,
            _service.config,
            tools,
            summary_context=body.summary_context,
        )
    finally:
        await tools.close()

    artifact = freeze_trade_plan(
        _service.strategy_store, plan, summary_context=body.summary_context,
    )
    return _artifact_to_dict(artifact)


@router.get("/trade-plan/{artifact_id}")
async def get_trade_plan(artifact_id: str) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    artifact = _service.strategy_store.get_artifact(artifact_id)
    if artifact is None or artifact.type != "trade_plan":
        raise HTTPException(status_code=404, detail=f"Trade plan {artifact_id} not found")
    return _artifact_to_dict(artifact)


@router.post("/trade-plan/{artifact_id}/approve")
async def approve_trade_plan_route(artifact_id: str, force: bool = False, approver: str = "") -> dict[str, Any]:
    """Promote a frozen trade plan to ACTIVE, gated by calibration (fail-closed).

    The gate is checked against persisted `calibration_entries` (Phase 7's write path via
    `POST .../record-outcome`), rebuilt fresh from storage on every call -- not an empty
    in-memory tracker. A plan with no realized-outcome history yet bootstraps off the
    symbol's own ACTIVE strategy artifact instead (see approve_trade_plan's docstring) --
    correctly rejected only when that's also missing.

    force=true (Stage 0, G2b): an explicit human override via Telegram/Discord's
    `/approve_plan` command -- requires `approver` (the requesting user's identity) so a
    forced approval is always distinguishable from a gate-cleared one in the logs.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        artifact = approve_trade_plan(_service.strategy_store, artifact_id, force=force, approver=approver)
    except TradePlanApprovalError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Trade plan failed the calibration gate", "reasons": e.reasons},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _artifact_to_dict(artifact)


@router.post("/decay/{artifact_id}/approve")
async def approve_decay_action_route(artifact_id: str, approver: str = "") -> dict[str, Any]:
    """Apply a `propose`-mode decay action recorded by ScheduledResearchExecutor
    .decay_scan() (VINU_RESEARCH_DECAY_RESPONSE_MODE=propose) -- this used to have
    no caller at all (no HTTP route, no CLI command), so a proposal recorded in
    `propose` mode had no way to actually be acted on short of a Python REPL.
    Mirrors approve_trade_plan_route's shape: `approver` is required (empty is a
    400, distinct from the 404 for "no such proposal" and 409 for "the artifact's
    status changed since the proposal, and the real lifecycle no longer allows
    this transition").
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    if not approver:
        raise HTTPException(status_code=400, detail="approver is required")
    try:
        artifact = approve_decay_action(_service.strategy_store, artifact_id, approver)
    except InvalidStatusTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _artifact_to_dict(artifact)


@router.post("/trade-score-calibration/approve")
async def approve_trade_score_calibration_route(approver: str = "") -> dict[str, Any]:
    """Apply a `propose`-mode TradeScore calibration recorded by
    ScheduledResearchExecutor.trade_score_calibration_scan()
    (VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE=propose). Mirrors
    approve_decay_action_route's exact shape -- `approver` required (empty
    is a 400), "no pending proposal" is a 404. Unlike decay approval, this
    isn't artifact-keyed: there is one global pending proposal (or none),
    so no artifact_id path parameter.
    """
    if not approver:
        raise HTTPException(status_code=400, detail="approver is required")
    try:
        thresholds = approve_trade_score_calibration(approver)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "confluence_max": thresholds.confluence_max,
        "ev_max": thresholds.ev_max,
        "risk_max": thresholds.risk_max,
        "regime_fit_max": thresholds.regime_fit_max,
    }


class UpdateInTradeActionRequest(BaseModel):
    action: str = Field(pattern=r"^(HOLD|ADD|REDUCE|EXIT)$")


@router.post("/trade-plan/{artifact_id}/action")
async def update_in_trade_action_route(artifact_id: str, body: UpdateInTradeActionRequest) -> dict[str, Any]:
    """Closes the loop TradeAction (HOLD/ADD/REDUCE/EXIT, high-expectations
    spec #10/#11) never had: vinu-live's classify_action() computes this
    every cycle but only ever annotated an ephemeral per-cycle dict --
    nothing persisted it back onto the artifact vinu-research owns. Called
    best-effort from vinu-live's orchestrator; failures here must never be
    able to affect a live cycle (hence 200-with-status rather than raising
    on a missing artifact -- this is telemetry, not a control action)."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    artifact = update_in_trade_action(_service.strategy_store, artifact_id, body.action)
    if artifact is None:
        return {"status": "not_persisted", "artifact_id": artifact_id}
    return {"status": "ok", "artifact_id": artifact_id, "in_trade_action": body.action}


class RecordOutcomeRequest(BaseModel):
    actual_return_pct: float


@router.post("/trade-plan/{artifact_id}/record-outcome")
async def record_outcome_route(artifact_id: str, body: RecordOutcomeRequest) -> dict[str, Any]:
    """Phase 7's write path: score a closed position's realized return against its frozen
    forecast and persist the calibration entry. Never triggers any live/in-trade action --
    consumed only at the next `approve_trade_plan` call or research cycle.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        entry = record_realized_outcome(
            _service.strategy_store, artifact_id, body.actual_return_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "artifact_id": entry.artifact_id,
        "forecast_direction": entry.forecast_direction,
        "actual_return_pct": entry.actual_return_pct,
        "directional_correct": entry.directional_correct,
        "brier_score": entry.brier_score,
        "magnitude_error": entry.magnitude_error,
        "timestamp": entry.timestamp,
    }


@router.get("/trade-plan/{artifact_id}/calibration")
async def get_trade_plan_calibration(artifact_id: str) -> dict[str, Any]:
    """Read back the calibration track record built from `.../record-outcome` calls.

    Consumed by vinu-portfolio's daily-allocation outcome-confidence tilt --
    this is the only read path for `calibration_entries`, previously write-only
    (only consumed in-process by `approve_trade_plan`'s gate check).
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    entries = _service.strategy_store.get_calibration_entries(artifact_id)
    result = compute_calibration(entries)
    return {
        "artifact_id": artifact_id,
        "n_entries": result.n_entries,
        "accuracy": result.accuracy,
        "brier_mean": result.brier_mean,
        "magnitude_mape": result.magnitude_mape,
        "passed": result.passed,
        "reasons": result.reasons,
    }


@router.get("/angle-calibration/{angle_name}")
async def get_angle_calibration_route(angle_name: str) -> dict[str, Any]:
    """Read-only aggregate for one angle's real forecast accuracy across
    every artifact it has ever been attributed to (Artifact.origin_angles,
    populated only from the research team's own final-answer JSON -- see
    trade_plan_authoring.py's record_realized_outcome). No pass/fail gate
    -- see AngleCalibrationResult's own docstring for why. An angle with
    no entries yet (never attributed, or attributed but nothing has
    closed) returns n_entries=0, not a 404 -- there is no meaningful
    distinction here between "unknown angle name" and "no data yet," and
    treating the former as an error would require a canonical angle-name
    registry that doesn't exist anywhere in this project.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = get_angle_calibration(_service.strategy_store, angle_name)
    return {
        "angle_name": angle_name,
        "n_entries": result.n_entries,
        "accuracy": result.accuracy,
        "brier_mean": result.brier_mean,
        "magnitude_mape": result.magnitude_mape,
    }
