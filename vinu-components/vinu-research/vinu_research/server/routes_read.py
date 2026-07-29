from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.models import ArtifactStatus
from vinu_research.promotion import meets_promotion_bar
from vinu_research.service import ResearchService

router = APIRouter()

_service = None


class RunResearchRequest(BaseModel):
    user_idea: str | None = Field(
        default=None, min_length=1,
        description="Strategy idea. If None, auto-proposed from angle context.",
    )
    strategy_code: str | None = Field(
        default=None,
        description="Pre-written strategy code. If provided, skips code generation and uses this as the starting point. user_idea is used as refinement context.",
    )
    symbol: str = Field(..., min_length=1, max_length=10)
    from_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    indicators: list[str] | None = None
    initial_capital: float | None = None
    dry_run: bool = False
    universe: list[str] | None = Field(
        default=None,
        description="Optional list of tickers to backtest as a portfolio alongside "
                    "`symbol`. When it has 2+ distinct symbols, the strategy runs "
                    "across the whole basket and the report includes a correlation "
                    "matrix and beta-hedge overlay.",
    )


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


@router.post("/run")
async def run_research(body: RunResearchRequest) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        result = await _service.run_research(
            user_idea=body.user_idea,
            strategy_code=body.strategy_code,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            indicators=body.indicators,
            initial_capital=body.initial_capital,
            dry_run=body.dry_run,
            universe=body.universe,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensure")
async def ensure_strategy(body: RunResearchRequest) -> dict[str, Any]:
    """Like /research/run, but skips running if `symbol` already has an
    ACTIVE/MONITORING strategy artifact — the "zero strategies" trigger."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        return await _service.ensure_strategy(
            user_idea=body.user_idea,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            indicators=body.indicators,
            initial_capital=body.initial_capital,
            dry_run=body.dry_run,
            universe=body.universe,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def list_runs(
    symbol: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return await _service.list_runs(symbol=symbol, status=status, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = await _service.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.delete("/runs/{run_id}")
async def delete_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    deleted = await _service.delete_run(run_id)
    return {"deleted": deleted, "run_id": run_id}


@router.get("/artifacts")
async def list_artifacts(
    status: str | None = None,
    type_: str | None = None,
) -> list[dict[str, Any]]:
    """List strategy artifacts, optionally filtered by status and/or type.

    Status can be a comma-separated list (e.g. "ACTIVE,MONITORING").
    Returns all artifacts when no filters are provided.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    statuses: list[ArtifactStatus] | None = None
    if status:
        try:
            statuses = [ArtifactStatus(s.strip()) for s in status.split(",") if s.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status value in '{status}'. Valid values: {[e.value for e in ArtifactStatus]}",
            )
    artifacts = _service.strategy_store.list_artifacts_by_statuses(
        statuses=statuses, type_=type_,
    )
    return [
        {
            "artifact_id": a.artifact_id,
            "type": a.type,
            "name": a.name,
            "universe": a.universe,
            "status": a.status.value,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
            "initial_sharpe": a.initial_sharpe,
            "initial_max_dd": a.initial_max_dd,
            "deflated_sharpe": a.deflated_sharpe,
            "holdout_passed": a.holdout_passed,
            "stress_test_passed": a.stress_test_passed,
        }
        for a in artifacts
    ]


@router.post("/artifacts/{artifact_id}/promote")
async def promote_artifact(artifact_id: str, force: bool = False) -> dict[str, Any]:
    """Transition a BENCHING artifact to ACTIVE.

    Refuses unless the artifact clears the promotion bar (deflated Sharpe +
    holdout check — see vinu_research.promotion) — pass force=true to
    override that check with an explicit human decision.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    artifact = _service.strategy_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    if artifact.status.value != "BENCHING":
        raise HTTPException(status_code=400, detail=f"Artifact is {artifact.status.value}, not BENCHING")
    verdict = meets_promotion_bar(artifact, _service.config)
    if not verdict.eligible and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Artifact does not meet the promotion bar; pass force=true to override",
                "reasons": verdict.reasons,
            },
        )
    artifact.status = ArtifactStatus.ACTIVE
    _service.strategy_store.upsert_artifact(artifact)
    return {
        "status": "promoted",
        "artifact_id": artifact_id,
        "forced": force and not verdict.eligible,
        "promotion_reasons": verdict.reasons,
    }


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = await _service.approve_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found or not in done status")
    return result
