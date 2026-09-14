import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from ..service import AgentService
from .schemas import StartSwarmRequest, SwarmRunResponse

LOG = logging.getLogger(__name__)

router = APIRouter()
_get_service: Any = lambda: None


def _get_runtime():
    svc: AgentService = _get_service()
    return svc.swarm_runtime


@router.post("/swarm/runs", response_model=SwarmRunResponse)
async def start_swarm(req: StartSwarmRequest):
    runtime = _get_runtime()
    try:
        run = runtime.create_run(req.preset_name, req.user_vars)
        runtime.start_run(run.run_id)
        return SwarmRunResponse(
            run_id=run.run_id,
            preset_name=run.preset_name,
            status=run.status.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/swarm/runs/latest")
async def get_latest_swarm_run(preset_name: str, symbol: str):
    """Most recent COMPLETED run for `preset_name` + `symbol`, or
    {"status": "none"} -- used cross-service by vinu-research's trade-plan
    authoring to opportunistically fold a completed investment_committee
    debate into the signal ledger. The debate itself is asynchronous
    (SwarmRuntime.start_run's own background thread) while authoring is a
    separate, later cycle in a different service, so this is a lookup, not
    a synchronous wait -- if nothing has completed yet, callers get "none"
    and simply proceed without a debate signal, same fail-open posture
    fetch_options_context/fetch_angle_signals already use on the
    vinu-research side.

    Registered BEFORE the `/swarm/runs/{run_id}` dynamic route below --
    FastAPI/Starlette match routes in registration order, so "latest" would
    otherwise be swallowed as a run_id path parameter by that route first.
    """
    runtime = _get_runtime()
    run = runtime.get_latest_run(preset_name, symbol)
    if run is None:
        return {"status": "none"}
    return {
        "status": "ok",
        "run_id": run.run_id,
        "preset_name": run.preset_name,
        "final_report": run.final_report,
        "tasks": [{"agent_name": t.agent_name, "role": t.role, "result": t.result} for t in run.tasks],
        "completed_at": run.completed_at,
    }


@router.post("/swarm/runs/ensure-fresh")
async def ensure_fresh_swarm_run(preset_name: str, symbol: str, max_age_minutes: float = 60.0):
    """In-trade thesis re-check (high-expectations follow-up): the
    investment_committee debate already produces a bull/bear verdict at
    entry time (see /swarm/runs/latest's own docstring) -- re-running it
    periodically for a symbol with an OPEN position and reading the
    freshest result *is* a thesis re-check, without a second LLM-reasoning
    pipeline. Returns whatever the latest run currently is (possibly None/
    stale) immediately; if it's missing or older than `max_age_minutes`, a
    new run is kicked off the same fire-and-forget way
    _start_investment_committee_debate does (create_run + start_run,
    background thread) so the NEXT call sees it -- this call never blocks
    waiting for the new run to finish."""
    runtime = _get_runtime()
    run = runtime.get_latest_run(preset_name, symbol)

    stale = True
    if run is not None and run.completed_at:
        try:
            completed = datetime.fromisoformat(run.completed_at)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            age_minutes = (datetime.now(timezone.utc) - completed).total_seconds() / 60.0
            stale = age_minutes > max_age_minutes
        except (TypeError, ValueError):
            stale = True

    if stale:
        try:
            new_run = runtime.create_run(preset_name, {"symbol": symbol})
            runtime.start_run(new_run.run_id)
        except Exception:
            LOG.exception(
                "Failed to start refresh run for %s/%s, returning existing result without it",
                preset_name, symbol,
            )

    if run is None:
        return {"status": "none"}
    return {
        "status": "ok",
        "run_id": run.run_id,
        "preset_name": run.preset_name,
        "final_report": run.final_report,
        "tasks": [{"agent_name": t.agent_name, "role": t.role, "result": t.result} for t in run.tasks],
        "completed_at": run.completed_at,
        "stale": stale,
    }


@router.get("/swarm/runs/{run_id}", response_model=SwarmRunResponse)
async def get_swarm_run(run_id: str):
    runtime = _get_runtime()
    run = runtime.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return SwarmRunResponse(
        run_id=run.run_id,
        preset_name=run.preset_name,
        status=run.status.value,
        final_report=run.final_report or None,
    )


@router.post("/swarm/runs/{run_id}/cancel")
async def cancel_swarm_run(run_id: str):
    runtime = _get_runtime()
    if not runtime.cancel_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found or already finished")
    return {"status": "cancelled"}


@router.get("/swarm/presets")
async def list_presets():
    runtime = _get_runtime()
    presets = runtime.list_presets()
    return {"presets": [p["name"] for p in presets]}
