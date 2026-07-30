"""Mutating hypothesis routes — creating a hypothesis and recording evidence
against it. Deliberately separate from routes_introspect.py (read-only) —
same split the codebase already uses elsewhere (routes_broker.py's mutating
/halt /resume /order vs. read-only status/account/positions routes).

Added as part of portfoli-mc-improvement Step 07 (optimizer-rules skill):
Step 02 only exposed a read-only `query_hypotheses` tool, but Step 07's
skill requires recording an expectation BEFORE seeing a sweep candidate's
result (so "was I right" is checkable afterward) — for candidates run
through Step 06's sweep engine, which calls ResearchTools.run_backtest
directly and does not go through StrategyResearchLoop.run()'s automatic
hypothesis/evidence writing. Without a write tool, that requirement was
undoable, not just undocumented.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Evidence, Hypothesis

router = APIRouter()


class CreateHypothesisRequest(BaseModel):
    title: str = Field(..., min_length=1)
    thesis: str = Field(..., min_length=1, description="The expectation/reasoning, recorded BEFORE seeing a result.")
    universe: list[str] = Field(default_factory=list)
    strategy_type: str = ""


class AddEvidenceRequest(BaseModel):
    run_id: int = 0
    iteration: int = 0
    metric: str = Field(..., min_length=1)
    value: float
    conclusion: str = Field(..., description="'supports' or 'contradicts' — was the thesis borne out?")
    reasoning: str = ""
    metrics_snapshot: dict[str, float] | None = None


def _serialize(h: Hypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": h.hypothesis_id,
        "title": h.title,
        "thesis": h.thesis,
        "status": h.status.value,
        "universe": h.universe,
        "strategy_type": h.strategy_type,
        "best_sharpe": h.best_sharpe,
        "evidence_count": len(h.evidence),
        "created_at": h.created_at,
        "updated_at": h.updated_at,
    }


@router.post("/hypotheses")
async def create_hypothesis(body: CreateHypothesisRequest) -> dict[str, Any]:
    """Record an expectation before seeing a result. Returns hypothesis_id —
    pass it to POST /hypotheses/{id}/evidence once the result is in."""
    reg = HypothesisRegistry()
    h = Hypothesis.create(title=body.title, thesis=body.thesis, universe=body.universe)
    if body.strategy_type:
        h.strategy_type = body.strategy_type
    reg.create(h)
    return _serialize(h)


@router.post("/hypotheses/{hypothesis_id}/evidence")
async def add_hypothesis_evidence(hypothesis_id: str, body: AddEvidenceRequest) -> dict[str, Any]:
    """Record an outcome against a previously-created hypothesis — what
    actually happened, so 'was the expectation correct' is checkable later
    via GET /research/hypotheses."""
    reg = HypothesisRegistry()
    evidence = Evidence(
        run_id=body.run_id,
        iteration=body.iteration,
        metric=body.metric,
        value=body.value,
        conclusion=body.conclusion,
        reasoning=body.reasoning,
        metrics_snapshot=body.metrics_snapshot,
    )
    h = reg.add_evidence(hypothesis_id, evidence)
    if h is None:
        raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")
    return _serialize(h)
