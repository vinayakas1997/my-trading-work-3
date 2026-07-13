from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from vinu_research.service import ResearchService

router = APIRouter()

_service = None


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


@router.post("/research/run")
async def run_research(
    user_idea: str = Query(...),
    symbol: str = Query(...),
    from_date: str = Query(...),
    to_date: str = Query(...),
    indicators: str | None = Query(default=None),
    initial_capital: float | None = Query(default=None),
    dry_run: bool = Query(default=False),
) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    indicator_list = [k.strip().lower() for k in indicators.split(",") if k.strip()] if indicators else None
    try:
        result = await _service.run_research(
            user_idea=user_idea,
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            indicators=indicator_list,
            initial_capital=initial_capital,
            dry_run=dry_run,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/runs")
async def list_runs(
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _service.list_runs(symbol=symbol, status=status, limit=limit)


@router.get("/research/runs/{run_id}")
async def get_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = _service.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.delete("/research/runs/{run_id}")
async def delete_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    deleted = _service.delete_run(run_id)
    return {"deleted": deleted, "run_id": run_id}
