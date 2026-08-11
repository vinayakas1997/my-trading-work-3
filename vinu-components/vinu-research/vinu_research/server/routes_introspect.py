"""Read-only introspection routes over agent-facing state that already exists
but, before this file, had no HTTP surface: hypothesis/evidence history,
per-symbol research-exhaustion state, and iteration checkpoints.

Added to give agent tools (and the LLM directly) read access to state that
was already being written but had no HTTP surface. The underlying data
(HypothesisRegistry, ResearchStorage's catalog/checkpoint tables) was
already written by the research loop; nothing here changes what gets
recorded, only what can be read back over HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus
from vinu_research.service import ResearchService

router = APIRouter()

_service: ResearchService | None = None


def set_service(svc: ResearchService) -> None:
    global _service
    _service = svc


def _serialize_hypothesis(h: Hypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": h.hypothesis_id,
        "title": h.title,
        "thesis": h.thesis,
        "status": h.status.value,
        "universe": h.universe,
        "strategy_type": h.strategy_type,
        "indicators_used": h.indicators_used,
        "params_tested": h.params_tested,
        "best_sharpe": h.best_sharpe,
        "invalidation_reason": h.invalidation_reason,
        "evidence_count": len(h.evidence),
        "evidence": [
            {
                "run_id": e.run_id,
                "iteration": e.iteration,
                "metric": e.metric,
                "value": e.value,
                "conclusion": e.conclusion,
                "reasoning": e.reasoning,
                "timestamp": e.timestamp,
                "source": e.source,
                "ref_id": e.ref_id,
            }
            for e in h.evidence
        ],
        "created_at": h.created_at,
        "updated_at": h.updated_at,
        "source": h.source,
    }


@router.get("/hypotheses")
async def list_hypotheses(
    symbol: str | None = Query(default=None, description="Filter to hypotheses whose universe includes this ticker"),
    status: str | None = Query(default=None, description="Filter by status: exploring|testing|validated|rejected|monitoring|mc_gate_failed"),
) -> dict[str, Any]:
    """Query recorded hypotheses and their evidence trail — what the agent
    expected before seeing a result, and whether it was borne out. Backed by
    the same HypothesisRegistry the research loop already writes to during
    every run() call; this route adds no new data, only a way to read it."""
    status_enum: HypothesisStatus | None = None
    if status:
        try:
            status_enum = HypothesisStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in HypothesisStatus]}",
            )
    reg = HypothesisRegistry()
    if symbol:
        hypotheses = reg.query_by_symbol(symbol, status=status_enum)
    else:
        hypotheses = reg.list_all(status=status_enum)
    return {"count": len(hypotheses), "hypotheses": [_serialize_hypothesis(h) for h in hypotheses]}


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str) -> dict[str, Any]:
    reg = HypothesisRegistry()
    h = reg.get(hypothesis_id)
    if h is None:
        raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")
    return _serialize_hypothesis(h)


@router.get("/symbols/{symbol}/state")
async def get_symbol_research_state(symbol: str) -> dict[str, Any]:
    """Whether a symbol is exhausted (too many failed trials without a
    passing strategy) plus its cross-run trial history, so an agent can
    decide whether starting new research on this symbol is worth it before
    spending a research run to find out."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    storage = _service.storage
    exhausted = storage.is_symbol_exhausted(symbol)
    entry = storage.get_catalog_entry(symbol)
    return {
        "symbol": symbol.upper(),
        "exhausted": exhausted,
        "catalog_entry": entry,
    }


@router.get("/runs/{run_id}/checkpoints")
async def get_run_checkpoints(
    run_id: int,
    latest_only: bool = Query(default=False, description="Return only the most recent checkpoint instead of the full list"),
) -> dict[str, Any]:
    """Iteration checkpoints saved during a research run() call — what
    resumability across sessions reads from. Note: as of Step 01's
    verification pass, loop.py only ever writes these; nothing currently
    resumes a run() from a saved checkpoint automatically, so this route is
    the first real consumer of this data."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    storage = _service.storage
    if latest_only:
        checkpoint = storage.get_last_checkpoint(run_id)
        return {"run_id": run_id, "checkpoint": checkpoint}
    checkpoints = storage.list_checkpoints(run_id)
    return {"run_id": run_id, "count": len(checkpoints), "checkpoints": checkpoints}
