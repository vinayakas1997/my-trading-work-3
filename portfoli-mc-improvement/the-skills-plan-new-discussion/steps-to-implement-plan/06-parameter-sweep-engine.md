---
name: 06-parameter-sweep-engine
status: Done
phase: 3
code: A1
depends_on: []
unlocks: [07-optimizer-rules-skill]
---

# Step 06 — Parameter Sweep Engine

## Why this step

This is Focus 1's actual centerpiece, and the one piece of this entire plan
confirmed, by direct code search, to not exist anywhere yet. We searched
`vinu-simulator` for `batch|permutation|sweep|grid` and found real Monte
Carlo code — but it's `monte_carlo_permutation`, which shuffles trade P&L
order to compute a statistical-significance p-value. That is a *different*
operation from what this step needs: running the same strategy repeatedly
with different numeric parameter *values* (SMA period, RSI thresholds,
ATR multipliers) to find good settings. No batch/grid runner for that
exists. This naming collision matters — keep calling this a "parameter
sweep," not "Monte Carlo," in code and docs, so it's never confused with
the validation Monte Carlo that already exists.

## What we're achieving

An engine capable of: given a strategy and a set of parameters to vary,
running it repeatedly through `vinu-simulator` at different parameter
values, and returning each candidate's full result (including the
`validation` block) for evaluation. Critically, per the earlier design
correction in this plan's history: **this engine executes single sweep
steps on request — it does not itself decide the search path.** The
adaptive coarse→fine, widen/narrow decision-making belongs to the agent,
using Step 07's skill and Step 08's governor. This step builds the thing
that *runs* a candidate, not the thing that *decides* which candidate to
try next.

## Where it matters in the future

This is the mechanical foundation Focus 1 is entirely built on. Steps 07
and 08 are meaningless without something real underneath them to call.

## How it connects to other steps

- **Independent build** — doesn't need Steps 01–05 finished first, can
  start any time; it's pure new engineering on `vinu-simulator`'s side.
- **Unlocks Step 07** — the optimizer-rules skill's whole job is deciding
  what to feed this engine next, round after round. Without this existing,
  Step 07 has nothing to drive.
- **Should return results in a shape Step 03's gatekeepers skill can
  consume directly** — coordinate the candidate-result schema with Step 03
  so there's no translation layer needed between "sweep engine returns a
  result" and "gatekeepers skill judges a result."

## Substeps

1. Decide where this lives: a new module inside `vinu-simulator` (natural
   fit — it already owns the backtest execution and validation logic) vs.
   a new orchestration layer in `vinu-agent` that calls the simulator
   repeatedly. Prefer inside `vinu-simulator` — keeps the "run one
   candidate" primitive close to the engine that already knows how to run
   and validate a single backtest.
2. Define the input contract: strategy name/config, the parameter(s) to
   vary this call and their value(s), fixed values for every other
   parameter, symbol, date range. This should look like "run this one
   candidate," not "run this whole sweep" — the sweep's shape (how many
   candidates, in what order) is Step 07's decision, made round by round.
3. Define the output contract: full `SimulationResult` including the
   `validation` block already computed by `_run_validation_and_attribution`
   — do not strip it down to just top-line metrics, since Step 03's
   gatekeepers skill needs the full statistical verdict.
4. Add a route (`vinu-simulator/server/routes_*.py`) if this needs to be
   callable over HTTP from the agent — check whether existing backtest
   routes already accept arbitrary parameter overrides, which might mean
   this step is smaller than expected (just documenting an existing
   capability) rather than building a new one. **Check this first**, before
   writing new engine code — it would not be the first time in this plan
   that something assumed missing turned out to already exist.
5. Add a corresponding `vinu-agent` tool (following Step 02's `BaseTool`
   pattern) so the agent can call "run this one candidate" directly.
6. Test: run a real strategy through this with 2–3 manually chosen
   parameter values, confirm real, distinct `validation` blocks come back
   for each.

## What was actually built

Substep 4's check paid off immediately: neither `SimulateRequest` nor
`CustomSimulateRequest` (vinu-simulator's two backtest entry points) has
any parameter-override field — confirmed by reading both Pydantic models
in full. But two other pieces of *existing* machinery turned out to cover
most of what this step needs, drastically narrowing the actual build:

- `vinu_research/generator.py::generate_strategy(recipe, params)` — already
  templates a numeric `params` dict into one of 15 built-in strategy
  recipes (`TEMPLATE_METADATA`: crossover, rsi, macd, bollinger_bands,
  supertrend, etc.), each with named, defaulted parameters
  (`fast_period`, `rsi_period`, `bb_std`, ...). This is exactly "generate
  a candidate at specific parameter values" for template-based strategies
  — reused directly, not reinvented.
- `vinu_research/tools.py::ResearchTools.run_backtest` — already posts to
  `/simulate/custom` with `run_validation=True` by default and returns a
  `BacktestResult` whose `.raw` dict carries the full `validation` block.
  So "run one candidate and get the full statistical verdict back" needed
  zero new simulator-side code — only a caller.

**What genuinely was new:** varying a parameter inside an *already-written*
strategy (e.g. one of Focus 2's LLM-generated candidates from a prior
research iteration, which isn't template-based) has no existing mechanism
— `generate_strategy` only works for its 15 known recipes. Built
`substitute_param_value()` (AST-based, not string replacement — walks the
parse tree for an `Assign` node targeting `param_name` or
`self.param_name` with a numeric `Constant` value and replaces it, so a
parameter name that happens to appear in a comment or string is never
touched) as the base-code-mode primitive.

**Files added:**
- `vinu_research/sweep.py` — `substitute_param_value`, `build_candidate_code`
  (dispatches recipe-mode vs. base-code-mode, rejects specifying both or
  neither), `run_sweep_candidate` (resolves code, calls
  `ResearchTools.run_backtest`, returns a `SweepCandidateResult` with
  `run_id`/`strategy_code`/`params_used`/`metrics`/`trade_count`/`validation`).
- `vinu_research/server/routes_sweep.py` — `POST /research/sweep/candidate`
  (runs one candidate, exactly one of `recipe`+`params` or
  `base_code`+`param_name`+`param_value` required) and
  `GET /research/sweep/recipes` (discovery — lists all 15 recipes with
  their tunable parameter names/defaults, via the existing
  `list_recipe_details()`).
- `vinu_agent/tools/run_sweep_candidate_tool.py` — `run_sweep_candidate`
  (`is_readonly=False`, matching `run_research`'s precedent — it executes
  a real backtest) and `list_sweep_recipes` (`is_readonly=True`).
- Wired into `vinu_research/server/app.py` (new router, `ResearchTools`
  instance shared with the route module).

**Bug found and reconfirmed, not fixed (same class as Step 02's finding):**
running the full `vinu-agent` test suite surfaced that `trade_plan_tool.py`
has the identical missing-`/research`-prefix bug already flagged as an
open item in Step 02 — its own test (`test_trade_plan_frozen.py`) expects
`/research/trade-plan/{symbol}` and fails against the actual
`/trade-plan/{symbol}` call. Left exactly as flagged in Step 02 — out of
this step's scope, tracked there.

**Unrelated pre-existing bug discovered, not fixed:** the full
`vinu-research` suite has 19 pre-existing failures, confirmed unrelated to
this step's changes (same 19 failures occur with this step's changes fully
reverted). Most notably `loop.py:288` raises `NameError: name 'time' is
not defined` inside `_check_goal_budget`'s setup — meaning any `run()`
call that passes a `Goal` object currently crashes. Flagged for whoever
next touches `loop.py` (most likely Step 07/08); out of scope to fix here.

## Definition of done

- [x] Confirmed (not assumed) that no existing route already does this —
      read both `SimulateRequest` and `CustomSimulateRequest` in full.
- [x] "Run one candidate with parameter overrides" implemented and callable
      via a new `vinu-agent` tool (`run_sweep_candidate`), in both
      recipe-mode and base-code-mode.
- [x] Output includes the full `validation` block — verified via unit
      tests with a mocked `ResearchTools.run_backtest` returning a
      populated `validation` dict, and via a live end-to-end route test
      (recipe generation + FastAPI route mounting) exercising the real
      `generate_strategy`/AST-substitution code paths. Not yet verified
      against a genuinely running `vinu-simulator` instance — flagged for
      whoever first runs this live, same caveat as Step 02's
      `get_backtest_validation` tool.
