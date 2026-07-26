from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.service import ResearchService
from vinu_research.tools import ResearchTools
from vinu_research.trade_plan_authoring import (
    TradePlanApprovalError,
    approve_trade_plan,
    author_trade_plan,
    freeze_trade_plan,
    record_realized_outcome,
)

router = APIRouter()

_service: ResearchService | None = None


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


class GenerateTradePlanRequest(BaseModel):
    timeframe: str = Field(default="daily", pattern=r"^(intraday|daily|swing)$")


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
    }


@router.post("/research/trade-plan/{symbol}")
async def generate_trade_plan(symbol: str, body: GenerateTradePlanRequest) -> dict[str, Any]:
    """Author + freeze a complete trade plan for `symbol` (status stays CREATED)."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    tools = ResearchTools(_service.config)
    try:
        plan = await author_trade_plan(symbol, body.timeframe, _service.config, tools)
    finally:
        await tools.close()

    artifact = freeze_trade_plan(_service.strategy_store, plan)
    return _artifact_to_dict(artifact)


@router.get("/research/trade-plan/{artifact_id}")
async def get_trade_plan(artifact_id: str) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    artifact = _service.strategy_store.get_artifact(artifact_id)
    if artifact is None or artifact.type != "trade_plan":
        raise HTTPException(status_code=404, detail=f"Trade plan {artifact_id} not found")
    return _artifact_to_dict(artifact)


@router.post("/research/trade-plan/{artifact_id}/approve")
async def approve_trade_plan_route(artifact_id: str) -> dict[str, Any]:
    """Promote a frozen trade plan to ACTIVE, gated by calibration (fail-closed).

    The gate is checked against persisted `calibration_entries` (Phase 7's write path via
    `POST .../record-outcome`), rebuilt fresh from storage on every call -- not an empty
    in-memory tracker. A plan with no realized-outcome history yet is correctly rejected.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        artifact = approve_trade_plan(_service.strategy_store, artifact_id)
    except TradePlanApprovalError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Trade plan failed the calibration gate", "reasons": e.reasons},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _artifact_to_dict(artifact)


class RecordOutcomeRequest(BaseModel):
    actual_return_pct: float


@router.post("/research/trade-plan/{artifact_id}/record-outcome")
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
