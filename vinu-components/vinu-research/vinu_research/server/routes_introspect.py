"""Read-only introspection routes over agent-facing state that already exists
but, before this file, had no HTTP surface: hypothesis/evidence history,
per-symbol research-exhaustion state, and iteration checkpoints.

Added to give agent tools (and the LLM directly) read access to state that
was already being written but had no HTTP surface. The underlying data
(HypothesisRegistry, ResearchStorage's catalog/checkpoint tables) was
already written by the research loop; nothing here changes what gets
recorded, only what can be read back over HTTP.

Empty-meaning contract (C5 -- the one place "what empty means" is stated
so no caller mistakes "no rows" for "not yet run"; every spelling pinned
by vinu-research/tests/test_empty_meanings.py, behavior unchanged):

- `outcome_status="passed"` -- a best result exists; `"no_strategy_found"`
  -- stopped with no best result and no infra signal (genuine, not an
  error); `"infra_failure"` -- the last iteration's reasoning carries the
  INFRASTRUCTURE FAILURE prefix (retry later, do not treat as a verdict).
- Per-candidate backtest `None` -- that one candidate's backtest raised;
  the rest still rank. All-`None` plus a recorded exception re-raises the
  exception (a real error surfaces, never a silent empty).
- Sweep `ranked=[]` with `completeness=0.0` -- every grid point failed;
  then `pbo` is `None` and `walk_forward` is skipped (`None`). (An empty
  grid itself is rejected with ValueError, not an empty result.)
- Sweep `pbo=None` -- fewer than 2 successful return columns to test.
- `walk_forward=None` -- skipped (disabled or nothing ranked) or zero
  completed windows.
- `sweep_id=""` -- this sweep was not persisted (`persist=False` or the
  persist write failed, which never fails the sweep itself); a non-empty
  uuid means a row exists in `sweep_grid_points`.
- Generation store `None`/disabled -- the round is not recorded;
  generation itself is unaffected (deliberate no-op, not a miswire).
- Eval `404` on one artifact -- never evaluated (expected state, read as
  "none on file"); by-ticker `count=0` -- nothing evaluated for the
  ticker (not an error). Agent-side eval context `""` -- env unset or
  nothing to report; the prompt is byte-identical without it.
- Paper-return `status` strings (`no_strategy_code_or_universe`,
  `backtest_failed: ...`, `backtest_returned_none`, `no_returns`) --
  degraded diagnostics with `daily_return=None`, never a crash.

Agent mapping rule: empties mean WAIT (nothing to act on yet) or DONE
(genuinely nothing found) -- only raised exceptions and transport errors
mean ERROR.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from vinu_infra.strategy_evaluation import resolve_strategy_evaluation_store
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.maturity_assessor import assess as assess_maturity
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


@router.get("/indicators/pool")
async def pool_indicator_evidence() -> dict[str, Any]:
    """item #8: whether a supporting indicator matters in general, across
    every strategy/hypothesis that used it, not siloed per-strategy. Reads
    HypothesisRegistry's existing evidence trail fresh on each call -- no
    new storage, same idiom as every other route in this file."""
    reg = HypothesisRegistry()
    return {"indicators": reg.pool_evidence_by_indicator()}


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


@router.get("/generation-rounds")
async def list_generation_rounds(symbol: str | None = None, limit: int = 50) -> dict[str, Any]:
    """item #16 finding #2: generation-time candidate loss now has a real
    persistence surface (generation_candidate_store.py) -- this is the
    read side, same "give read access to state that was already being
    written but had no HTTP surface" idiom as every other route in this
    file. Header rows only; see GET /generation-rounds/{generation_id}
    for one round's full point-by-point detail."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return {"rounds": _service.generation_candidate_store.list_rounds(symbol=symbol, limit=limit)}


@router.get("/generation-rounds/{generation_id}")
async def get_generation_round(generation_id: str) -> dict[str, Any]:
    """Every candidate drafted in one generation/refinement call, winner
    included -- "why this round went the way it did," not just which
    strategy code an iteration ended up using."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    round_ = _service.generation_candidate_store.get_round(generation_id)
    if round_ is None:
        raise HTTPException(status_code=404, detail="no generation round found for this generation_id")
    return round_


@router.get("/candidate-graveyard/{symbol}")
async def get_candidate_graveyard(symbol: str, limit: int = 50) -> dict[str, Any]:
    """item #16 finding #3 (missing-pieces-of-system/new-theory-of-
    trading/system-wide-audit-and-design/
    02-open-questions-strategy-and-simulation.md): "has something like
    this already failed, and why" across all three of this codebase's
    real death points for a research idea -- generation-time (heuristic
    ranking discard), sweep-time (a failed backtest point), and
    hypothesis-level rejection. A read-time query
    (candidate_graveyard.py), not a fourth store: none of the three
    underlying stores change, this just lets them be asked about
    together. The sweep store is read via routes_sweep's own
    already-wired instance (get_sweep_store()) rather than constructing
    a second connection against the same on-disk file."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    from vinu_research.candidate_graveyard import query_candidate_graveyard
    from vinu_research.server.routes_sweep import get_sweep_store

    sweep_store = get_sweep_store()
    if sweep_store is None:
        raise HTTPException(status_code=503, detail="sweep store not configured")

    entries = query_candidate_graveyard(
        symbol.upper(),
        generation_store=_service.generation_candidate_store,
        sweep_store=sweep_store,
        hypothesis_registry=HypothesisRegistry(),
        limit=limit,
    )
    return {"symbol": symbol.upper(), "count": len(entries), "entries": entries}


@router.get("/maturity/status")
async def get_maturity_status() -> dict[str, Any]:
    """The first real HTTP surface for `MaturityAssessor` -- previously
    only reachable in-process (`trade_plan_authoring.py`'s own prompt-
    context wiring). `00-maturity-agentic-system-explanation.md` itself
    named this exact route ("a small HTTP endpoint, e.g. GET
    /maturity/status, for cross-service callers") as the intended shape
    for a service with no in-process bridge to vinu-research -- built
    now for `vinu-live`'s risk_gatekeeper/live_decision consumers.
    Always available (read-only, no side effects); each consumer
    decides independently, via its own config knob, whether to actually
    act on the tier -- this route itself is not gated by
    `maturity_tier_enabled` (that flag only ever controlled whether
    trade-plan authoring's own LLM prompt includes it)."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    config = _service.config
    assessment = assess_maturity(
        _service.strategy_store, config.agent_data_root,
        mature_min_trades=config.trade_score_calibration_min_sample,
    )
    return assessment.as_prompt_dict()


@router.get("/evaluation-status/{artifact_id}")
async def get_evaluation_status(artifact_id: str) -> dict[str, Any]:
    """item #2 (system-wide-audit-and-design): "why isn't this trading"
    already has a real, correct answer -- `StrategyEvaluationStore`
    already consolidates every gate a candidate strategy/trade plan
    passes through (risk_critic, correlation_gate, trade_score_gate,
    calibration_gate, capital_allocator, order_guard, ...) into one
    current-state view (`status`, `rejected_at_step`, `rejected_reason`),
    recomputed on every write. It just had no HTTP surface anywhere --
    this is that surface, not a new gate or a new abstraction."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    store = resolve_strategy_evaluation_store(_service.config.data_root)
    status = store.get_status(artifact_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"no evaluation status for artifact {artifact_id}")
    return status


@router.get("/evaluation-status/by-ticker/{ticker}")
async def list_evaluation_status_for_ticker(ticker: str) -> dict[str, Any]:
    """Every artifact evaluated for this ticker, newest first -- "what's
    currently blocking (or has already cleared) trading on this
    symbol," across every candidate, not just one."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    store = resolve_strategy_evaluation_store(_service.config.data_root)
    statuses = store.list_status_for_ticker(ticker)
    return {"ticker": ticker.upper(), "count": len(statuses), "statuses": statuses}


@router.get("/evaluation-history/{artifact_id}")
async def get_evaluation_history(artifact_id: str) -> dict[str, Any]:
    """The full step-by-step trail behind `get_evaluation_status`'s
    current-state summary -- every gate this artifact was actually run
    through, in order, with each one's own verdict and reasoning."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    store = resolve_strategy_evaluation_store(_service.config.data_root)
    history = store.get_history(artifact_id)
    return {"artifact_id": artifact_id, "count": len(history), "history": history}


@router.get("/pipeline-edges")
async def get_pipeline_edges(only_problems: bool = False) -> dict[str, Any]:
    """Phase 3 of the-inconsistencies-v2 plan: which declared pipeline connections are actually
    flowing at runtime. Joins the edge manifest (`vinu-infra/pipeline_edges.yaml`: what SHOULD flow
    where, with known gaps) with what the instrumented consumers recorded
    (`vinu_infra.pipeline_edge_recorder`: received / empty / stale / missing, with age and counts).

    `state` per edge: known_gap (declared unwired), not_instrumented (no recording call site yet --
    silence says nothing), never_seen (instrumented, nothing ever recorded: producer or consumer
    never ran), flowing, empty (empty where it should not be), stale (older than the edge's
    `stale_after_sec`), missing (the last read failed). `only_problems=true` returns just the edges
    that need attention. Read-only; reports presence and age, NOT whether a value that arrived is
    correct. Recording needs a shared root (VINU_EDGE_DATA_ROOT, or the VINU_STRATEGY_EVAL_DATA_ROOT
    research/live/agent already share) -- without one this reports `recording_enabled: false`."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    from vinu_infra import pipeline_edge_recorder as recorder
    from vinu_infra import pipeline_edges

    store = recorder.resolve_edge_status_store()  # no fallback: a private root would show nothing and mislead
    try:
        edges = pipeline_edges.load_edges()
    except Exception as exc:  # noqa: BLE001 -- a missing/garbled manifest must not 500 a read route
        return {
            "recording_enabled": store is not None, "manifest": "unavailable", "error": str(exc),
            "states": store.list_states() if store is not None else [],
        }
    report = recorder.edges_flow_report(edges, store)
    flagged = recorder.not_flowing(report)
    return {
        "recording_enabled": store is not None,
        "count": len(report),
        "not_flowing": len(flagged),
        "edges": flagged if only_problems else report,
    }


@router.get("/parity-report")
async def get_parity_report(min_days: int = 20, min_trades: int = 30) -> dict[str, Any]:
    """v2 A3: does what a strategy / forecast promised match what it then delivered? Read-only and advisory.

    `strategies`: each strategy artifact's backtest Sharpe / max drawdown against its paper days (Sharpe with a
    standard error, so a short window says so). **The paper series is the strategy's code re-run on new days, not
    real fills**, so this is out-of-sample stability, not execution parity (slippage, spread, fills). `trade_plans`:
    mean stated confidence vs realized hit rate, and forecast magnitude vs realized move, over closed live trades.
    Paper days come from vinu-agent's paper_performance.db when `agent_data_root` is mounted here, else from the
    agent API; `paper_source` says which."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    import httpx

    from vinu_research import parity_report as pr
    from vinu_research.models import ArtifactStatus

    store = _service.strategy_store
    statuses = (ArtifactStatus.BENCHING, ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING, ArtifactStatus.DECAYED)
    strategies = [a for st in statuses for a in store.list_artifacts(status=st, type_="strategy")]

    paper_source = "db"
    paper = pr.read_paper_returns_db(_service.config.agent_data_root)
    if paper is None:
        paper_source, paper = "agent_api", {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                for a in strategies:
                    try:
                        resp = await client.get(f"{_service.config.agent_api_url}/agent/broker/performance/{a.artifact_id}")
                        if resp.status_code == 200:
                            paper[a.artifact_id] = resp.json().get("daily_returns") or []
                    except Exception:  # noqa: BLE001 -- one artifact's failure must not hide the others
                        continue
        except Exception:  # noqa: BLE001
            paper_source = "unavailable"
    try:
        entries = store.list_all_calibration_entries()
    except Exception:  # noqa: BLE001 -- a store problem must not 500 a read route
        entries = []
    report = pr.build_parity_report(strategies, paper, entries, min_days=min_days, min_trades=min_trades)
    report["paper_source"] = paper_source
    return report
