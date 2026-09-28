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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from vinu_research.service import ResearchService
from vinu_research.track2_aggregate import compute_track2_aggregate
from vinu_research.track2_reconciliation import list_unconfirmed_moves

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


class RecordMoveEventRequest(BaseModel):
    bar_ts: int
    window_seconds: int
    granularity: str
    atr: float
    price_move: float
    move_threshold: float
    direction: str


@router.post("/move-evidence/{symbol}")
async def record_move_event_route(symbol: str, body: RecordMoveEventRequest) -> dict[str, Any]:
    """Track 2's own writer (item #10) -- called by vinu-live's poller on
    every candle close where `detect_move()` found a real move, whether
    or not any strategy's must-condition also fired for the same window.
    Unlike `.../signal-evidence/trigger`, no duplicate-id rejection: a
    move event isn't keyed by a caller-supplied id, each call is its own
    real detection."""
    svc = _require_service()
    event_id = svc.move_evidence_store.record_move_event(
        symbol,
        bar_ts=body.bar_ts, window_seconds=body.window_seconds, granularity=body.granularity,
        atr=body.atr, price_move=body.price_move, move_threshold=body.move_threshold,
        direction=body.direction,
    )
    return {"id": event_id, "symbol": symbol, "status": "recorded"}


@router.get("/move-evidence")
async def list_move_events_route(symbol: str | None = None, limit: int = 50) -> dict[str, Any]:
    svc = _require_service()
    events = svc.move_evidence_store.list_move_events(symbol, limit)
    return {"events": events, "count": len(events)}


@router.get("/unconfirmed-moves")
async def list_unconfirmed_moves_route(symbol: str | None = None, limit: int = 50) -> dict[str, Any]:
    """item #10: real Track 2 moves with no matching Track 1 trigger on
    file -- the `track2_only` case. See track2_reconciliation.py's own
    docstring for the honest caveat about what this looks like today
    (nothing yet writes Track 1 triggers in production, so most/all real
    moves currently show up here)."""
    svc = _require_service()
    events = list_unconfirmed_moves(
        move_evidence_store=svc.move_evidence_store,
        signal_evidence_store=svc.signal_evidence_store,
        symbol=symbol, limit=limit,
    )
    return {"events": events, "count": len(events)}


@router.get("/track2-aggregate/{symbol}")
async def track2_aggregate_route(
    symbol: str,
    must_condition: str,
    as_of: int | None = Query(
        default=None,
        description=(
            "Pin the effective 'now' this aggregate reflects (unix seconds) "
            "-- only evidence whose outcome was known by this instant is "
            "included, so a simulator can call this without lookahead. "
            "Omitted means everything resolved so far."
        ),
    ),
    min_sample_size: int = 5,
) -> dict[str, Any]:
    """items #4 and #10 of 02-open-questions-strategy-and-simulation.md:
    the one computed evidence-confidence number both the simulator's
    sizing and live_decision's cross-track disagreement check need --
    built once here, read by both rather than reimplemented twice."""
    svc = _require_service()
    return compute_track2_aggregate(
        symbol, must_condition,
        evidence_store=svc.signal_evidence_store,
        as_of=as_of,
        min_sample_size=min_sample_size,
    )
