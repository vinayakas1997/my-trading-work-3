---
name: optimizer-rules
description: How to run an adaptive Monte Carlo parameter search for a strategy — coarse-to-fine, widen when a parameter isn't sensitive, narrow when it is. Parameter knowledge lives in rules.yaml.
category: tool
---

## Optimizer Rules — Adaptive Monte Carlo Parameter Search

This skill tells the agent how to search a strategy's parameter space
through `vinu-simulator`, and how to decide when it's done.

`rules.yaml` is **not** a fixed sweep plan. It is a knowledge library: what
parameters a strategy exposes, what kind of parameter each one is (a moving
average period, a threshold ratio, a multiplier, ...), and what a sane
*starting* step looks like for that kind. The agent decides the actual
search path at runtime from what it observes — the same way it'd pull a
fact from a library, not follow a fixed script.

It depends on the `gatekeepers` skill — every candidate parameter set is
judged against the gatekeepers named in that strategy's `gatekeepers_required`
list. Load both skills before searching.

### The adaptive search algorithm

1. Load `rules.yaml` via `load_support_file("rules.yaml")`. Look up the
   strategy under `strategies`. If it isn't listed, stop and say so rather
   than guessing a parameter space.
2. For each parameter, resolve its `param_type` against `parameter_library`
   to get a starting `seed_step` and `seed_bounds`. These are a reasonable
   first guess, not the final search space.
3. Run a **coarse pass**: sweep each parameter at its seed step across its
   seed bounds, holding other parameters at a sane default.
4. Read the outcome and judge sensitivity per parameter:
   - **Low sensitivity** (the objective barely moves across the whole
     coarse pass, or keeps improving monotonically toward one edge of the
     bounds) → the current window is probably wrong, not the parameter
     itself. Widen the bounds outward (e.g. push 5+ steps past whichever
     edge kept improving) and re-run the coarse pass in the new region.
   - **High sensitivity** (the objective swings meaningfully between
     adjacent coarse points, with a visible peak) → narrow the step
     (finer resolution, e.g. half the seed step) and re-run around the
     best-performing coarse point(s) to refine it.
   - **No sensitivity even after widening** → the parameter isn't doing
     useful work for this strategy/market; fix it at its default and stop
     searching that dimension.
5. Repeat step 4 (widen or narrow, per parameter, independently) until
   either:
   - `max_iterations` (from `defaults.convergence` or the strategy's
     override) is reached, or
   - No improvement in the primary objective for
     `stop_if_no_improvement_for` consecutive rounds.
6. For every candidate produced along the way, evaluate it via
   `gatekeepers` (only the ids listed in `gatekeepers_required` for this
   strategy). Converge on the best candidate that passes all `hard`
   gatekeepers. If none pass, report that clearly — do not silently
   return a gatekeeper-failing result as "the best one."

**Worked example** (matches the SMA9/SMA200 case this skill was written
around): a strategy exposes two moving-average period parameters, `sma9`
and `sma200`, both typed `moving_average_period` in the library (seed step
1, seed bounds ±5 around the default). The coarse pass on `sma9` shows a
clear peak — narrow the step to refine around it. The coarse pass on
`sma200` shows almost no change across the whole ±5 window — that's a
signal the window is too narrow for a 200-period average to matter, not
that the parameter is useless. Widen `sma200`'s bounds well past ±5 (e.g.
±50) and re-run the coarse pass there before concluding anything.

### Primary objective

Unless a strategy overrides it, rank passing candidates by `sharpe_oos`
descending, then by `maxdd_oos` ascending as a tiebreaker.

### Adding a new strategy to the search

Add an entry under `strategies` in `rules.yaml`: list its parameters and
which `param_type` each one maps to in `parameter_library` (add a new
`param_type` there if none fits — don't invent a one-off shape inline),
plus which gatekeeper ids apply. Don't hardcode a strategy's parameter
space in code — this file is the single source of truth so the agent can
add new strategies without a code change.
