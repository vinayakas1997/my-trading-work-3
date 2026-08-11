"""Parameter sweep engine routes — run one strategy candidate at one set of
numeric parameter values. See vinu_research/sweep.py for the engine itself
and why this is deliberately not called "Monte Carlo."
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from vinu_research.generator import list_recipe_details
from vinu_research.sweep import ParameterNotFoundError, SweepCandidateResult, run_sweep_candidate
from vinu_research.sweep_grid import GridTooLargeError, SweepGridResult, run_sweep_grid
from vinu_research.tools import ResearchTools

router = APIRouter()

_tools: ResearchTools | None = None


def set_tools(tools: ResearchTools) -> None:
    global _tools
    _tools = tools


class SweepCandidateRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    from_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    recipe: str | None = Field(default=None, description="A BUILTIN_RECIPES key (see GET /sweep/recipes). Requires `params`.")
    params: dict[str, float] | None = Field(default=None, description="Full parameter dict for this candidate (recipe mode) — fixed + varied values.")

    base_code: str | None = Field(default=None, description="Existing strategy code to vary one parameter of (base-code mode). Requires `param_name`/`param_value`.")
    param_name: str | None = None
    param_value: float | None = None

    indicators: list[str] | None = None
    initial_capital: float | None = None

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> "SweepCandidateRequest":
        recipe_mode = self.recipe is not None
        base_code_mode = self.base_code is not None
        if recipe_mode == base_code_mode:
            raise ValueError(
                "Specify exactly one of `recipe` (with `params`) or `base_code` "
                "(with `param_name`/`param_value`)."
            )
        return self


def _serialize(result: SweepCandidateResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "strategy_name": result.strategy_name,
        "strategy_code": result.strategy_code,
        "params_used": result.params_used,
        "metrics": result.metrics,
        "trade_count": result.trade_count,
        "validation": result.validation,
    }


@router.post("/sweep/candidate")
async def sweep_candidate(body: SweepCandidateRequest) -> dict[str, Any]:
    """Run exactly one backtest at one set of parameter values. Does not
    decide what to try next — that's the caller's (agent's) job, using the
    optimizer-rules skill and the governor, round after round."""
    try:
        result = await run_sweep_candidate(
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            recipe=body.recipe,
            params=body.params,
            base_code=body.base_code,
            param_name=body.param_name,
            param_value=body.param_value,
            indicators=body.indicators,
            initial_capital=body.initial_capital,
            tools=_tools,
        )
    except ParameterNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return _serialize(result)


@router.get("/sweep/recipes")
async def sweep_recipes() -> dict[str, Any]:
    """Discover available recipe-mode strategies and their tunable
    parameter names/defaults — what an agent should read before picking a
    `recipe` + `params` for POST /sweep/candidate."""
    return {"recipes": list_recipe_details()}


class SweepGridRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    from_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    param_grid: list[dict[str, float]] = Field(..., min_length=1, description="One full params dict (recipe mode) per grid point, or a dict containing at least `param_name` (base-code mode).")

    recipe: str | None = Field(default=None, description="A BUILTIN_RECIPES key. Requires each param_grid entry to carry the full parameter set.")
    base_code: str | None = Field(default=None, description="Existing strategy code to vary one parameter of (base-code mode). Requires `param_name`.")
    param_name: str | None = None

    indicators: list[str] | None = None
    initial_capital: float | None = None

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> "SweepGridRequest":
        recipe_mode = self.recipe is not None
        base_code_mode = self.base_code is not None
        if recipe_mode == base_code_mode:
            raise ValueError(
                "Specify exactly one of `recipe` or `base_code` (with `param_name`)."
            )
        if base_code_mode and self.param_name is None:
            raise ValueError("base_code mode requires `param_name`.")
        return self


def _serialize_grid(result: SweepGridResult) -> dict[str, Any]:
    return {
        "requested": result.requested,
        "succeeded": result.succeeded,
        "completeness": result.completeness,
        "pbo": result.pbo,
        "ranked": [
            {
                "params": r.params,
                "score": r.score,
                "risk_score": r.risk_score,
                "complexity_score": r.complexity_score,
                "run_id": r.sweep_result.run_id,
                "strategy_code": r.sweep_result.strategy_code,
                "metrics": r.sweep_result.metrics,
                "trade_count": r.sweep_result.trade_count,
            }
            for r in result.ranked
        ],
        "failed_points": [
            {"params": o.params, "error": o.error} for o in result.outcomes if not o.succeeded
        ],
    }


@router.post("/sweep/grid")
async def sweep_grid(body: SweepGridRequest) -> dict[str, Any]:
    """Run a whole parameter grid in one call and return a ranked table
    plus a PBO overfitting estimate -- the primitive Phase 1
    (New-talk-agents/new-thinking/new-restructure/phases/
    phase-1-sweep-engine-wiring/) wires into idea_generator/backtest_runner
    so the LLM makes ONE round-trip for a whole sweep round, not one per
    grid point. See sweep_grid.py for completeness/PBO semantics."""
    try:
        result = await run_sweep_grid(
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            param_grid=body.param_grid,
            recipe=body.recipe,
            base_code=body.base_code,
            param_name=body.param_name,
            indicators=body.indicators,
            initial_capital=body.initial_capital,
            tools=_tools,
        )
    except GridTooLargeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _serialize_grid(result)
