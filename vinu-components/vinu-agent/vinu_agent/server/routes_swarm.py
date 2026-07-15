from typing import Any

from fastapi import APIRouter, HTTPException

from ..service import AgentService
from .schemas import StartSwarmRequest, SwarmRunResponse

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
