---
name: 06-parameter-sweep-engine
status: Not Started
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

## Open risks / assumptions

- Substep 4's check is important — re-verify against current
  `vinu-simulator` routes before assuming this is greenfield. The earlier
  grep only checked for `batch|permutation|sweep|grid` as literal strings;
  a parameter-override capability might exist under different naming.

## Definition of done

- [ ] Confirmed (not assumed) that no existing route already does this.
- [ ] "Run one candidate with parameter overrides" implemented and callable
      via a new `vinu-agent` tool.
- [ ] Output includes the full `validation` block, verified against a real
      run, not a mocked one.
