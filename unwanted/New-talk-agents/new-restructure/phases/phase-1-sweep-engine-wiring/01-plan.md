---
name: phase-1-plan
status: built -- the wiring this plan describes has landed; see the correction note on registration below
purpose: deep-dive plan for Phase 1 -- wiring the already-built, already-tested sweep engine into the real research team, replacing raw LLM code generation as the default. This is the fix for the two real bugs that started this whole redesign.
---

> **Correction note (implementation-plan task 09, verified against code):** the
> registration mechanism described below as "add to `build_registry`" is wrong.
> There is no explicit registration list. `tools/__init__.py`'s `build_registry`
> **auto-discovers** every `BaseTool` subclass defined inside the `tools/`
> package (`_discover_subclasses()` → `BaseTool.__subclasses__()` filtered to
> `tools.` modules, then `check_available()`), so a tool is visible to agents
> the instant its module exists in `tools/`. The only explicit wiring is which
> team's tool list names it. The plan's outcome is correct and is now built
> (`run_parameter_sweep` exists and is on the research team's `backtest_runner`
> toolset); only the "add it to the registry" framing was inaccurate.

# Phase 1 -- Fix the actual bug

## Why this phase exists

The real-LLM test that kicked off this whole design effort found two
concrete bugs in `idea_generator`'s output: it misread `generate_weights`
as per-bar instead of whole-window, and it hallucinated angle field names
(`arima_forecast`, etc.) as if they were backtest DataFrame columns. Both
came from the same root cause -- the LLM hand-writes strategy code from
scratch every time, with nothing deterministic checking its work before a
real backtest runs against it. This phase fixes the cause, not the two
symptoms individually.

**Scoping note:** this phase operates entirely inside the real, already-
built `research` team (`teams/research/manager_prompt.md`,
`agents/idea_generator/`, `agents/backtest_runner/`, `agents/risk_critic/`)
-- it does **not** require Phase 6's Planner triage layer to exist first.
Recipe selection happens inside `idea_generator` itself in this phase (it
already has tools to look at real data; adding `list_sweep_recipes` to
that toolset is a small addition, not a new stage). When the Planner
lands later, recipe-picking can move upstream to it -- this phase doesn't
need to wait for that.

## What's already built and confirmed real, just unwired

- `vinu-research/sweep.py`'s `run_sweep_candidate` -- AST-based parameter
  substitution (`substitute_param_value`), not string hacking, can't
  corrupt code. Runs one candidate at a fixed parameter point.
- `vinu-research/comparison.py`'s `rank_candidates` -- ranks a set of
  already-run candidates. Built, unused.
- `vinu-research/pbo.py` -- probability-of-backtest-overfitting
  calculation. Built, unused.
- `vinu-research/generator.py`'s `BUILTIN_RECIPES` -- a real set of
  pre-defined strategy shapes with parameter spaces.
- `vinu_agent/tools/run_sweep_candidate_tool.py` -- `RunSweepCandidateTool`
  and `ListSweepRecipesTool`, both real and tested. On registration: there is
  **no explicit tool list to add to** -- `tools/__init__.py` auto-discovers
  every `BaseTool` subclass defined in the `tools/` package. The real gap at
  this phase's start was assignment: these tools were on no team's tool list,
  so no agent could see them.

**Before writing any code in this phase:** re-read the exact signatures of
`run_sweep_candidate`, `rank_candidates`, `pbo.py`'s entry point, and
`BUILTIN_RECIPES`'s shape directly from the files -- don't implement
against a remembered description. This plan describes what each piece
does, not its exact call signature.

## What this phase changes

**1. Make the existing tools visible to the research team.** Registration is
automatic (`tools/__init__.py` auto-discovers `BaseTool` subclasses defined in
the `tools/` package), so nothing gets added to a hardcoded registry -- the step
that actually matters is naming the tools in the `research` team's tool list
(`teams/research/TEAM.md`) so agents can call them. This alone makes the built-
but-invisible infrastructure usable -- do this first, before writing any new
wrapper.

**2. `idea_generator` tries a recipe before writing raw code.** Update
`teams/research/agents/idea_generator/prompt.md` so the default path is:
call `list_sweep_recipes`, check whether any recipe's shape fits the
hypothesis being explored, and if so, pick the recipe plus a coarse
parameter range instead of writing `generate_weights` by hand. Raw code
generation becomes the **exception path** -- only for ideas no recipe
covers -- not the default it is today.

**3. New thin wrapper: `run_parameter_sweep`.** A new tool (e.g.
`vinu_agent/tools/run_parameter_sweep_tool.py`) that loops
`run_sweep_candidate` internally over a parameter grid and returns one
ranked table (via `comparison.py`'s `rank_candidates`) in a single tool
call -- instead of the LLM making one round-trip per grid point. This is
the change that actually removes hand-written-code-per-attempt from the
loop; `run_sweep_candidate` alone still requires an LLM turn per point,
the wrapper is what makes it deterministic and cheap.

**4. `backtest_runner`'s role expands to include self-verdict (role c).**
Reads the ranked table from `run_parameter_sweep` plus `pbo.py`'s
overfitting probability, and decides PASS/FAIL -- same verdict shape
`risk_critic` already uses today (reused, not reinvented, so nothing
downstream needs a new verdict format).

**5. Update `manager_prompt.md`.** Reflect the new step ordering (recipe
attempt -> sweep -> ranked table -> self-verdict, with raw code-gen only
on the exception path) and add the round cap described below.

## The round cap (real problem, real fix)

The sweep-refine loop (propose a parameter region, sweep it, look at the
ranked results, maybe narrow and sweep again) is a genuine internal loop
with no natural stopping point. Left open-ended, one stubborn candidate
could burn far more calls than the rest of the pipeline combined. Fix:
cap it at N rounds, reusing the exact `max_iterations` pattern the real
`research` team's manager loop already enforces today (same mechanism,
not a new one) -- `manager_prompt.md` already says "you'll be told your
iteration limit," this just applies that same budget concept to the
inner sweep-refine loop specifically, not only the outer idea-retry loop.

## Fail-closed completeness

`run_parameter_sweep` must report a `completeness` field: N of M grid
points that actually succeeded. The self-verdict step (role c) treats
anything below 100% (or an explicit, stated tolerance) as automatic FAIL
-- never a ranked PASS off partial results. This matters because the
underlying simulator is already known to silently zero-fill a failed
candidate rather than error loudly (confirmed behavior from the earlier
indicators-column bug investigation) -- without this check, a data hiccup
mid-sweep could produce a false PASS that looks statistically clean.
