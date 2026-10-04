from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
import ast

from pydantic import BaseModel, Field, field_validator

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
    interval: str | None = Field(
        default=None, pattern=r"^(1m|5m|15m|30m|1h|4h|1d|1wk)$",
        description="Bar size for this run only (default: the service's own). A strategy meant for 15-minute bars must be "
                    "judged on 15-minute bars.",
    )

    @field_validator("strategy_code")
    @classmethod
    def _seed_code_must_define_user_strategy(cls, value: str | None) -> str | None:
        """The research loop always asks the simulator for a class named `UserStrategy`. A seed that defines another
        name used to be accepted and then died minutes later as an "infrastructure failure" (HTTP 422 from the
        simulator) after the LLM calls had already been paid for. Reject it up front, with the reason."""
        if value is None:
            return value
        try:
            tree = ast.parse(value)
        except SyntaxError as exc:
            raise ValueError(f"strategy_code is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        if not any(isinstance(n, ast.ClassDef) and n.name == "UserStrategy" for n in ast.walk(tree)):
            raise ValueError("strategy_code must define a class named UserStrategy (the research loop runs that name)")
        return value
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
            interval=body.interval,
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
            "pbo": a.pbo,
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
    correlation_verdict = await _service.build_correlation_verdict(artifact)
    verdict = meets_promotion_bar(artifact, _service.config, correlation_verdict)

    # missing-pieces-of-system/startegy-enhancer/01-plan.md section 2 --
    # a real, third call site found while implementing the K-cap fix
    # (2026-09-21): this HTTP route and `promote-scan` are both real
    # BENCHING->ACTIVE paths, and this one had never been wired at all.
    ticker = artifact.universe[0] if artifact.universe else ""
    try:
        import os
        from pathlib import Path

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore, seed_step_registry

        eval_root = os.environ.get("VINU_STRATEGY_EVAL_DATA_ROOT", "").strip()
        if eval_root and ticker:
            eval_store = StrategyEvaluationStore(Path(eval_root) / "strategy_evaluation.db")
            seed_step_registry(eval_store)
            if correlation_verdict is not None:
                eval_store.write_step_result(
                    artifact_id=artifact_id, ticker=ticker, step_name="correlation_gate",
                    step_order=3, verdict="PASS" if correlation_verdict.eligible else "FAIL",
                    reasoning="; ".join(correlation_verdict.reasons) if correlation_verdict.reasons else "within correlation threshold",
                    metrics={
                        "avg_correlation": correlation_verdict.avg_correlation,
                        "max_correlation": correlation_verdict.max_correlation,
                        "n_active": correlation_verdict.n_active,
                    },
                )
            eval_store.write_step_result(
                artifact_id=artifact_id, ticker=ticker, step_name="promotion_bar",
                step_order=2, verdict="PASS" if verdict.eligible else "FAIL",
                reasoning="; ".join(verdict.reasons) if verdict.reasons else "cleared promotion bar",
                metrics={
                    "deflated_sharpe": artifact.deflated_sharpe,
                    "holdout_passed": artifact.holdout_passed,
                    "stress_test_passed": artifact.stress_test_passed,
                },
            )
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "failed to write strategy_evaluation rows for %s, continuing without them", artifact_id,
        )

    if not verdict.eligible and not force:
        # Real fix, same reasoning as promote-scan/capital_allocator_hook.py:
        # deflated_sharpe/holdout/pbo are fixed metrics from this artifact's
        # own backtest -- a genuine (non-forced) rejection is permanent, so
        # DISABLE it rather than leaving it stuck in BENCHING forever
        # blocking a K-cap slot.
        artifact.status = ArtifactStatus.DISABLED
        _service.strategy_store.upsert_artifact(artifact)
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


@router.get("/artifacts/{artifact_id}/paper-return")
async def get_paper_return(artifact_id: str, lookback_days: int = 10) -> dict[str, Any]:
    """The most recent trading day's realized return `artifact`'s
    strategy_code would have produced, for vinu-live's ShadowEvaluator to
    accumulate as one day of paper performance.

    This is the write-side input ShadowEvaluator's promotion gate has
    always needed but never had a real producer for -- nothing in
    production ever computed a BENCHING artifact's daily paper return, so
    PaperPerformanceStore stayed permanently empty and no artifact could
    ever accumulate min_paper_days (see high-expectations gate-conflict
    audit). Reuses the same backtest path revalidate_artifact() already
    uses (ResearchTools.run_backtest), over a short trailing window rather
    than building a second paper-execution engine, and reads the
    simulator's own daily_returns series (CustomSimulateResponse.
    daily_returns, chronologically ordered) rather than re-deriving
    per-day PnL independently.
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    artifact = _service.strategy_store.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    if not artifact.strategy_code or not artifact.universe:
        return {"artifact_id": artifact_id, "status": "no_strategy_code_or_universe", "daily_return": None}

    from datetime import datetime, timedelta, timezone

    from vinu_research.tools import ResearchTools

    symbol = artifact.universe[0]
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    tools = ResearchTools(_service.config)
    try:
        result = await tools.run_backtest(
            strategy_code=artifact.strategy_code,
            strategy_class_name="CustomStrategy",
            symbols=[symbol],
            from_date=from_date,
            to_date=to_date,
            run_validation=False,
        )
    except Exception as e:
        return {"artifact_id": artifact_id, "status": f"backtest_failed: {e}", "daily_return": None}
    finally:
        await tools.close()

    if result is None:
        return {"artifact_id": artifact_id, "status": "backtest_returned_none", "daily_return": None}
    returns = result.raw.get("daily_returns") if isinstance(result.raw, dict) else None
    if not returns:
        return {"artifact_id": artifact_id, "status": "no_returns", "daily_return": None}
    return {
        "artifact_id": artifact_id, "status": "ok",
        "daily_return": returns[-1], "trade_date": to_date, "symbol": symbol,
    }


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: int) -> dict[str, Any]:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    result = await _service.approve_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found or not in done status")
    return result


# ------------------------------------------------------------------------------ live-decision strategy validation

class StrategyValidationRequest(BaseModel):
    name: str = Field(..., min_length=1)
    schedule: str | None = None
    universe: list[str] = Field(default_factory=list)
    must_conditions: list[dict[str, Any]] = Field(default_factory=list)
    live_decision_max_hold_bars: int = 0
    from_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


_validation_tasks: set = set()


@router.post("/strategy-validations")
async def start_strategy_validation(body: StrategyValidationRequest) -> dict[str, Any]:
    """Send a live-decision strategy through the research and simulation gates (strategy_validation.py). Runs in the
    background (minutes: one research run per ticker); poll GET /research/strategy-validations for the verdict."""
    import asyncio
    from datetime import date, timedelta

    from vinu_research.strategy_validation import validate_strategy

    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    end = body.to_date or date.today().isoformat()
    start = body.from_date or (date.today() - timedelta(days=4 * 365 + 30)).isoformat()
    definition = body.model_dump()
    task = asyncio.create_task(validate_strategy(_service, definition, start, end))
    _validation_tasks.add(task)
    task.add_done_callback(_validation_tasks.discard)
    return {"status": "started", "strategy_id": body.name, "window": [start, end]}


@router.get("/strategy-validations")
async def list_strategy_validations() -> dict[str, Any]:
    """Every live-decision strategy's validation verdict: validated, rejected, unvalidatable or running. The live loop
    reads this and only evaluates strategies (and tickers) that are validated for their exact current rules."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    rows = _service.strategy_validation_store.list()
    return {"validations": rows, "count": len(rows)}
