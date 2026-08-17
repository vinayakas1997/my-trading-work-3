"""Runs a whole SET of sweep candidates in one call and returns a ranked
table plus a PBO overfitting estimate -- the "many points, one round"
primitive New-talk-agents/new-thinking/new-restructure/phases/
phase-1-sweep-engine-wiring/ wires into the research team, built on top of
sweep.py's run_sweep_candidate (one point), comparison.py's rank_candidates,
and pbo.py's probability_of_backtest_overfitting. Deliberately a separate
module from sweep.py: sweep.py's own docstring states it never decides what
to try next or when to stop -- this module still doesn't decide EITHER
(the caller supplies the exact grid), it just runs a bounded, explicit list
of points in one round-trip instead of one LLM turn per point.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

LOG = logging.getLogger(__name__)

from vinu_research.comparison import RankedCandidate, rank_candidates
from vinu_research.config import ResearchConfig
from vinu_research.models import BacktestMetrics, BacktestResult, LlmCandidate
from vinu_research.pbo import probability_of_backtest_overfitting
from vinu_research.sweep import ParameterNotFoundError, SweepCandidateResult, run_sweep_candidate
from vinu_research.tools import ResearchTools

# Grid-size cap: bounds how many points run_sweep_grid will run in a SINGLE
# round -- independent of the round cap the research team's manager loop
# enforces on the outer sweep-refine loop (narrow, re-sweep, repeat). Each
# point here is a real backtest call to vinu-simulator; without this,
# round 1 alone could be arbitrarily expensive regardless of the round cap.
# See phase-1-guard-rail.md: "three different caps... don't conflate them."
MAX_GRID_POINTS = int(os.environ.get("VINU_RESEARCH_SWEEP_GRID_MAX_POINTS", "20"))

# CSCV (pbo.py) needs at least n_splits*2 periods to produce a real
# estimate -- below that it already returns a neutral 0.5 dict rather than
# erroring, so no extra guard is needed here beyond having >= 2 candidates.
_MIN_CANDIDATES_FOR_PBO = 2


class GridTooLargeError(ValueError):
    """Raised when the requested grid exceeds MAX_GRID_POINTS. Never
    silently truncated -- a silent truncation would be exactly the kind of
    "completeness lies about what was actually asked for" case the
    completeness field itself exists to catch."""


@dataclass
class GridPointOutcome:
    params: dict[str, Any]
    succeeded: bool
    error: str = ""
    sweep_result: SweepCandidateResult | None = None


@dataclass
class RankedSweepCandidate:
    """comparison.rank_candidates' RankedCandidate only carries the
    LlmCandidate (code/params/reasoning) + scores -- it never had a
    SweepCandidateResult to link back to before this module existed. This
    pairs the two so a caller can report the top candidate's real run_id/
    metrics/trade_count, not just its score."""

    score: float
    risk_score: float
    complexity_score: float
    params: dict[str, Any]
    sweep_result: SweepCandidateResult


@dataclass
class SweepGridResult:
    requested: int
    succeeded: int
    completeness: float
    ranked: list[RankedSweepCandidate]
    pbo: dict[str, float] | None
    outcomes: list[GridPointOutcome] = field(default_factory=list)
    walk_forward: dict[str, Any] | None = None


async def run_sweep_grid(
    *,
    symbol: str,
    from_date: str,
    to_date: str,
    param_grid: list[dict[str, Any]],
    recipe: str | None = None,
    base_code: str | None = None,
    param_name: str | None = None,
    indicators: list[str] | None = None,
    initial_capital: float | None = None,
    config: ResearchConfig | None = None,
    tools: ResearchTools | None = None,
) -> SweepGridResult:
    """Run every point in `param_grid` (each a full params dict for recipe
    mode, or a dict containing at least `param_name` for base-code mode),
    rank the successes, and estimate overfitting risk across them.

    `completeness`'s denominator is always `len(param_grid)` (what was
    REQUESTED), never how many points happened to succeed -- a point that
    fails to run (e.g. substitute_param_value can't parameterize it) still
    counts against completeness rather than silently shrinking the
    denominator. See phase-1-guard-rail.md.
    """
    if not param_grid:
        raise ValueError("param_grid must contain at least one point.")
    if len(param_grid) > MAX_GRID_POINTS:
        raise GridTooLargeError(
            f"Requested grid has {len(param_grid)} points, exceeding the "
            f"per-round cap of {MAX_GRID_POINTS}. Narrow the grid (fewer "
            f"points or a coarser range) and try again -- this cap is "
            f"separate from the outer sweep-refine loop's round cap."
        )

    recipe_mode = recipe is not None
    base_code_mode = base_code is not None
    if recipe_mode == base_code_mode:
        raise ValueError("Specify exactly one of `recipe` or `base_code`.")
    if base_code_mode and param_name is None:
        raise ValueError("base_code mode requires `param_name`.")

    resolved_tools = tools or ResearchTools(config)
    requested = len(param_grid)

    outcomes: list[GridPointOutcome] = []
    for point in param_grid:
        try:
            if recipe_mode:
                sweep_result = await run_sweep_candidate(
                    symbol=symbol, from_date=from_date, to_date=to_date,
                    recipe=recipe, params=point,
                    indicators=indicators, initial_capital=initial_capital,
                    tools=resolved_tools,
                )
            else:
                if param_name not in point:
                    raise ValueError(f"Grid point missing required key '{param_name}': {point}")
                sweep_result = await run_sweep_candidate(
                    symbol=symbol, from_date=from_date, to_date=to_date,
                    base_code=base_code, param_name=param_name, param_value=point[param_name],
                    indicators=indicators, initial_capital=initial_capital,
                    tools=resolved_tools,
                )
            outcomes.append(GridPointOutcome(params=point, succeeded=True, sweep_result=sweep_result))
        except (ParameterNotFoundError, ValueError, RuntimeError) as exc:
            outcomes.append(GridPointOutcome(params=point, succeeded=False, error=str(exc)))

    succeeded_outcomes = [o for o in outcomes if o.succeeded]
    succeeded = len(succeeded_outcomes)
    completeness = succeeded / requested if requested else 0.0

    candidates: list[LlmCandidate] = []
    backtest_results: list[BacktestResult | None] = []
    returns_columns: list[np.ndarray] = []
    # Keyed by id() of the LlmCandidate instance -- rank_candidates()
    # returns RankedCandidate objects wrapping these same instances (just
    # re-sorted), so this is how the sweep_result each one came from gets
    # found again after ranking, without changing comparison.py's own
    # RankedCandidate shape (shared with the non-grid ranking path too).
    candidate_to_sweep_result: dict[int, SweepCandidateResult] = {}
    for o in succeeded_outcomes:
        sr = o.sweep_result
        assert sr is not None
        candidate = LlmCandidate(code=sr.strategy_code, params=sr.params_used)
        candidates.append(candidate)
        candidate_to_sweep_result[id(candidate)] = sr
        metrics = BacktestMetrics.from_dict(sr.metrics)
        equity_points = int(sr.raw.get("equity_points", 0))
        backtest_results.append(BacktestResult(
            run_id=sr.run_id,
            strategy_name=sr.strategy_name,
            metrics=metrics,
            benchmark_metrics=sr.raw.get("benchmark_metrics", {}),
            trade_count=sr.trade_count,
            equity_points=equity_points,
            raw=sr.raw,
        ))
        daily_returns = sr.raw.get("daily_returns") or []
        if daily_returns:
            returns_columns.append(np.array(daily_returns, dtype=float))

    raw_ranked: list[RankedCandidate] = rank_candidates(candidates, backtest_results) if candidates else []
    ranked = [
        RankedSweepCandidate(
            score=r.score,
            risk_score=r.risk_score,
            complexity_score=r.complexity_score,
            params=r.candidate.params,
            sweep_result=candidate_to_sweep_result[id(r.candidate)],
        )
        for r in raw_ranked
    ]

    pbo_result: dict[str, float] | None = None
    if len(returns_columns) >= _MIN_CANDIDATES_FOR_PBO:
        # Trim to the shortest column -- candidates can have slightly
        # different real return-series lengths (e.g. a run with fewer
        # tradeable days near a data boundary); PBO's CSCV needs a
        # rectangular matrix, and trimming to the common overlap is a
        # defensible simplification, not silently fabricated data.
        min_len = min(len(c) for c in returns_columns)
        if min_len > 0:
            matrix = np.column_stack([c[:min_len] for c in returns_columns])
            pbo_result = probability_of_backtest_overfitting(matrix)

    walk_forward_result: dict[str, Any] | None = None
    if config is not None and config.walk_forward_enabled and ranked:
        from vinu_research.walk_forward import run_walk_forward

        try:
            wf = await run_walk_forward(
                symbol=symbol, from_date=from_date, to_date=to_date,
                param_grid=param_grid, recipe=recipe, base_code=base_code,
                param_name=param_name, indicators=indicators,
                initial_capital=initial_capital, config=config,
                tools=resolved_tools,
            )
            if wf is not None:
                walk_forward_result = wf.to_dict()
        except Exception:
            LOG.exception("Walk-forward pass failed, sweep result carries no walk-forward evidence")

    return SweepGridResult(
        requested=requested,
        succeeded=succeeded,
        completeness=completeness,
        ranked=ranked,
        pbo=pbo_result,
        outcomes=outcomes,
        walk_forward=walk_forward_result,
    )


def sweep_evidence_verdict(
    completeness: float,
    pbo: dict[str, float] | None,
    walk_forward: dict[str, Any] | None,
    *,
    completeness_tolerance: float = 0.95,
    pbo_severe: float = 0.7,
) -> dict[str, Any]:
    """Deterministic PASS/FAIL gate that folds all three evidence signals a
    recipe-path run can produce -- completeness, PBO, and the walk-forward
    stability verdict -- into a single call. Fail-closed: any missing or
    failing signal pushes toward FAIL, and a walk-forward verdict of FAIL is
    an automatic overall FAIL even if PBO looked fine (a parameter set can
    be PBO-clean yet still unstable window to window -- that is exactly the
    failure mode implementation-plan task 06 / shortcoming #8 targets).

    The backtest_runner prompt instructs the LLM to treat this as an
    automatic override on top of its own written reasoning."""
    reasons: list[str] = []
    if completeness < completeness_tolerance:
        reasons.append(
            f"incomplete grid: completeness {completeness:.2f} below {completeness_tolerance:.2f}"
        )
    if pbo is None:
        reasons.append("no PBO estimate available")
    elif pbo.get("pbo") is not None and pbo["pbo"] > pbo_severe:
        reasons.append(f"PBO {pbo['pbo']:.2f} above severe threshold {pbo_severe:.2f}")
    if walk_forward is None:
        reasons.append("no walk-forward stability evidence available")
    elif not walk_forward.get("stability_verdict", {}).get("passed", False):
        reasons.append("walk-forward stability verdict FAIL")
    return {
        "passed": not reasons,
        "reasons": reasons or ["completeness, PBO and walk-forward stability all within tolerance"],
        "completeness": round(completeness, 4),
        "pbo": pbo,
        "walk_forward": walk_forward,
    }
