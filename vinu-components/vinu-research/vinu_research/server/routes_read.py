from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.service import ResearchService

router = APIRouter()

_service = None


class RunResearchRequest(BaseModel):
    user_idea: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1, max_length=10)
    from_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    indicators: list[str] | None = None
    initial_capital: float | None = None
    dry_run: bool = False


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


@router.post("/research/run")
async def run_research(body: RunResearchRequest) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        result = await _service.run_research(
            user_idea=body.user_idea,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            indicators=body.indicators,
            initial_capital=body.initial_capital,
            dry_run=body.dry_run,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/runs")
async def list_runs(
    symbol: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await _service.list_runs(symbol=symbol, status=status, limit=limit)


@router.get("/research/runs/{run_id}")
async def get_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = await _service.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.delete("/research/runs/{run_id}")
async def delete_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    deleted = await _service.delete_run(run_id)
    return {"deleted": deleted, "run_id": run_id}
