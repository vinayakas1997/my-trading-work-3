from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, Field

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

    app.include_router(router)
    return app
