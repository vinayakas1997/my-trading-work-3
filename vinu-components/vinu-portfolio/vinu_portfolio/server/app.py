from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field

from vinu_infra.auth import require_auth
from vinu_portfolio.service import PortfolioService


class BatchCandidate(BaseModel):
    """One PEND artifact vinu-agent's capital_allocator wants evaluated
    alongside the real active book -- see evaluate_batch below."""

    artifact_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    symbol: str = ""


class EvaluateBatchRequest(BaseModel):
    candidates: list[BatchCandidate] = Field(..., min_length=1)
    daily_allocation: bool = Field(
        default=False,
        description="If true, run the regime/outcome-tilted daily allocation on top of the base risk-parity weights instead of returning the base weights alone.",
    )


def create_app() -> FastAPI:
    app = FastAPI(title="vinu-portfolio", version="0.1.0")
    _service = PortfolioService()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await _service.close()

    router = APIRouter(prefix="/portfolio")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "vinu-portfolio"}

    @router.get("/state")
    async def get_portfolio() -> dict[str, Any]:
        return await _service.build_portfolio()

    @router.get("/strategies")
    async def list_strategies() -> list[dict[str, Any]]:
        return await _service.list_active_strategies()

    @router.get("/weights")
    async def get_weights() -> list[dict[str, Any]]:
        portfolio = await _service.build_portfolio()
        return portfolio.get("weights", [])

    @router.get("/daily-allocation")
    async def get_daily_allocation() -> dict[str, Any]:
        return await _service.compute_daily_allocation()

    @router.get("/allocation-history")
    async def get_allocation_history(limit: int = 30) -> dict[str, Any]:
        """Persisted daily allocations, newest first (one summary line each). Read-only."""
        rows = _service.allocation_history_summaries(limit=limit)
        return {"count": len(rows), "allocations": rows}

    @router.get("/not-funded")
    async def get_not_funded() -> dict[str, Any]:
        """Why candidates were left unfunded in the most recent recorded daily allocation.
        `status: none` means no allocation has been recorded yet (not an error)."""
        latest = _service.latest_not_funded()
        if latest is None:
            return {"status": "none", "count": 0, "not_funded": []}
        return {"status": "ok", **latest}

    @router.get("/daily-game-plan")
    async def get_daily_game_plan() -> dict[str, Any]:
        return await _service.compute_daily_game_plan()

    @router.get("/risk/status")
    async def get_risk_status() -> dict[str, Any]:
        return await _service.compute_risk_status()

    @router.post("/evaluate-batch")
    async def evaluate_batch(body: EvaluateBatchRequest) -> dict[str, Any]:
        """vinu-agent Phase 2 (capital_allocator's PEND batch, see
        New-talk-agents/new-thinking/new-restructure/phases/
        phase-2-funding-mechanics/): compute real risk-parity weights (and
        correlation, including PEND-vs-PEND within this same batch) for a
        set of candidates that are NOT yet ACTIVE, alongside the real
        active book -- without needing them to be ACTIVE first."""
        extra_candidates = [
            {
                "name": c.name,
                "kind": "llm_python",
                "symbol": c.symbol,
                "artifact_id": c.artifact_id,
                "weights_source": f"artifact:{c.artifact_id}",
                "is_candidate": True,
            }
            for c in body.candidates
        ]
        if body.daily_allocation:
            return await _service.compute_daily_allocation(extra_candidates=extra_candidates)
        return await _service.build_portfolio(extra_candidates=extra_candidates)

    app.include_router(router, dependencies=[Depends(require_auth)])
    return app
