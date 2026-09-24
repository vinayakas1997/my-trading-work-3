"""HTTP surface for SignalEvidenceStore -- Phase 2 of
missing-pieces-of-system/new-theory-of-trading (Decisions 1, 2, 3, 7, 8).

Mirrors the same wiring pattern routes_trade_plan.py's
`.../record-outcome` already uses for calibration: vinu-live detects a
real event live (there, a closed position; here, a must-condition
trigger) and POSTs it to vinu-research over HTTP, which owns storage.
Nothing new architecturally -- this is that same proven pattern applied
to the new evidence table.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.service import ResearchService

router = APIRouter()

_service: ResearchService | None = None


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


def _require_service() -> ResearchService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _service


class RecordTriggerRequest(BaseModel):
    trigger_id: str
    symbol: str
    trigger_time: str
    must_condition: str | list[str]
    indicators: dict[str, Any] = Field(default_factory=dict)
    granularity: str = "15min"
    policy_version: str | None = None


class RecordEvidenceOutcomeRequest(BaseModel):
    max_favorable_excursion: float
    max_adverse_excursion: float
    return_at_horizon: float


@router.post("/signal-evidence/trigger")
async def record_trigger_route(body: RecordTriggerRequest) -> dict[str, Any]:
    """Called once, at the moment a must-condition fires -- records the raw
    snapshot (Decision 1: raw values, no bucketing/derivation here) of
    every supporting indicator available at that instant. Outcome fields
    stay NULL until `.../outcome` is called later, once the recording
    horizon has actually elapsed."""
    svc = _require_service()
    store = svc.signal_evidence_store
    if store.get_trigger(body.trigger_id) is not None:
        raise HTTPException(status_code=409, detail=f"trigger_id {body.trigger_id!r} already recorded")
    store.record_trigger(
        body.trigger_id, body.symbol, body.trigger_time, body.must_condition, body.indicators,
        granularity=body.granularity, policy_version=body.policy_version,
    )
    return {"trigger_id": body.trigger_id, "status": "recorded"}


@router.post("/signal-evidence/{trigger_id}/outcome")
async def record_evidence_outcome_route(trigger_id: str, body: RecordEvidenceOutcomeRequest) -> dict[str, Any]:
    svc = _require_service()
    store = svc.signal_evidence_store
    if store.get_trigger(trigger_id) is None:
        raise HTTPException(status_code=404, detail=f"trigger_id {trigger_id!r} not found")
    store.record_outcome(
        trigger_id,
        max_favorable_excursion=body.max_favorable_excursion,
        max_adverse_excursion=body.max_adverse_excursion,
        return_at_horizon=body.return_at_horizon,
    )
    return {"trigger_id": trigger_id, "status": "outcome_recorded"}


@router.get("/signal-evidence/{trigger_id}")
async def get_signal_evidence_route(trigger_id: str) -> dict[str, Any]:
    svc = _require_service()
    row = svc.signal_evidence_store.get_trigger(trigger_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"trigger_id {trigger_id!r} not found")
    return row


@router.get("/signal-evidence")
async def list_signal_evidence_route(symbol: str | None = None, limit: int = 50) -> dict[str, Any]:
    svc = _require_service()
    rows = svc.signal_evidence_store.list_triggers(symbol, limit)
    return {"triggers": rows, "count": len(rows)}
