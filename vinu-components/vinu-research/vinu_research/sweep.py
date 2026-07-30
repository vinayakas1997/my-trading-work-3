"""Parameter sweep engine — runs ONE strategy candidate at a specific set of
numeric parameter values and returns its full, validated backtest result.

Deliberately named "sweep", not "Monte Carlo" — vinu-simulator already has a
`monte_carlo_permutation` function that means something else entirely
(shuffling trade P&L order to compute a significance p-value). This module
varies strategy PARAMETER VALUES (SMA period, RSI threshold, ...), which is
a different operation. See
portfoli-mc-improvement/the-skills-plan-new-discussion/steps-to-implement-plan/06-parameter-sweep-engine.md.

This module deliberately does NOT decide which parameter values to try next
or when to stop — that adaptive, coarse-to-fine reasoning belongs to the
`optimizer-rules` skill (Step 07) and the governor (Step 08), which use this
module's `run_sweep_candidate` as a primitive: "run this one candidate,"
called repeatedly, round by round.

Two ways to produce the candidate's code, both converging on the same
`ResearchTools.run_backtest` call:

- **Recipe mode** — `recipe` is a `vinu_research.generator.BUILTIN_RECIPES`
  key (e.g. "crossover", "rsi"). Parameter values are spliced into the
  template via the existing `generate_strategy(recipe=..., params=...)` —
  reused, not reinvented. Use `list_recipe_details()` to discover a recipe's
  tunable parameter names and defaults.
- **Base-code mode** — `base_code` is an existing, already-generated
  strategy (e.g. LLM-authored, from a prior research iteration) that is not
  template-based. `param_name`/`param_value` locate and replace a single
  numeric assignment (`param_name = <number>` or `self.param_name = <number>`)
  via AST — not string replacement, so it can't accidentally match text
  inside a comment or string literal. Every other assignment in the code is
  left untouched.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from typing import Any

from vinu_research.config import ResearchConfig
from vinu_research.generator import BUILTIN_RECIPES, generate_strategy
from vinu_research.tools import ResearchTools


class ParameterNotFoundError(ValueError):
    """Raised when `param_name` has no matching numeric assignment in `base_code`."""


@dataclass
class SweepCandidateResult:
    run_id: str
    strategy_name: str
    strategy_code: str
    params_used: dict[str, Any]
    metrics: dict[str, Any]
    trade_count: int
    validation: dict[str, Any] | None
    raw: dict[str, Any] = field(default_factory=dict)


def substitute_param_value(code: str, param_name: str, new_value: float | int) -> str:
    """Replace every numeric-constant assignment to `param_name` (or
    `self.param_name`) in `code` with `new_value`, via AST — not text
    substitution, so a parameter name that happens to appear inside a
    string or comment is never touched.

    Raises ParameterNotFoundError if no matching assignment exists, so a
    caller never silently gets back code identical to what it passed in.
    """
    tree = ast.parse(code)
    found = False

    def _target_matches(target: ast.expr) -> bool:
        if isinstance(target, ast.Name):
            return target.id == param_name
        if isinstance(target, ast.Attribute):
            return target.attr == param_name
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(_target_matches(t) for t in node.targets):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, (int, float)):
            continue
        node.value = ast.copy_location(ast.Constant(value=new_value), node.value)
        found = True

    if not found:
        raise ParameterNotFoundError(
            f"No numeric assignment to '{param_name}' (or 'self.{param_name}') "
            f"found in the given code — cannot substitute a value for a "
            f"parameter that isn't there."
        )

    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def build_candidate_code(
    *,
    recipe: str | None = None,
    params: dict[str, Any] | None = None,
    base_code: str | None = None,
    param_name: str | None = None,
    param_value: float | int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve either recipe-mode or base-code-mode inputs into a concrete
    strategy_code string plus the params actually used. Exactly one mode
    must be specified — mixing both is a caller error, not silently resolved
    by picking one.
    """
    recipe_mode = recipe is not None
    base_code_mode = base_code is not None

    if recipe_mode == base_code_mode:
        raise ValueError(
            "Specify exactly one of `recipe` (with `params`) or `base_code` "
            "(with `param_name`/`param_value`) — not both, not neither."
        )

    if recipe_mode:
        if recipe not in BUILTIN_RECIPES:
            known = ", ".join(sorted(BUILTIN_RECIPES))
            raise ValueError(f"Unknown recipe '{recipe}'. Known recipes: {known}")
        code = generate_strategy(recipe=recipe, params=params)
        return code, dict(params or {})

    if param_name is None or param_value is None:
        raise ValueError("base_code mode requires both `param_name` and `param_value`.")
    code = substitute_param_value(base_code, param_name, param_value)
    return code, {param_name: param_value}


async def run_sweep_candidate(
    *,
    symbol: str,
    from_date: str,
    to_date: str,
    recipe: str | None = None,
    params: dict[str, Any] | None = None,
    base_code: str | None = None,
    param_name: str | None = None,
    param_value: float | int | None = None,
    indicators: list[str] | None = None,
    initial_capital: float | None = None,
    config: ResearchConfig | None = None,
    tools: ResearchTools | None = None,
) -> SweepCandidateResult:
    """Run exactly one backtest at one set of parameter values and return
    its full result, including the statistical validation block. Does not
    decide what to try next — see this module's docstring."""
    strategy_code, params_used = build_candidate_code(
        recipe=recipe, params=params,
        base_code=base_code, param_name=param_name, param_value=param_value,
    )

    resolved_tools = tools or ResearchTools(config)
    result = await resolved_tools.run_backtest(
        strategy_code=strategy_code,
        strategy_class_name="UserStrategy",
        symbols=[symbol],
        from_date=from_date,
        to_date=to_date,
        indicators=indicators,
        initial_capital=initial_capital,
        run_validation=True,
    )
    if result is None:
        raise RuntimeError("Backtest returned no result (simulator unreachable or rejected the candidate).")

    return SweepCandidateResult(
        run_id=result.run_id,
        strategy_name=result.strategy_name,
        strategy_code=strategy_code,
        params_used=params_used,
        metrics=asdict(result.metrics),
        trade_count=result.trade_count,
        validation=result.raw.get("validation"),
        raw=result.raw,
    )
