---
name: optimizer-rules
description: How to adaptively search a strategy's numeric parameter space using the real sweep engine, gatekeepers, hypothesis tracking, and strategy-tags skills — coarse-to-fine, widen when a parameter isn't sensitive, narrow when it is. Parameter-type knowledge lives in rules.yaml.
category: tool
---

## Optimizer Rules — Adaptive Parameter Search (Focus 1)

This skill tells the agent how to search a strategy's parameter space and
how to decide when it's done. It is the first skill in this project that
composes all of the others — read `gatekeepers/SKILL.md` and
`strategy-tags/SKILL.md` before using this one; they're referenced
throughout, not restated.

`rules.yaml` is **not** a fixed sweep plan and does not list strategies —
that was tried in an earlier draft and abandoned once Step 06's sweep
engine turned out to already expose a real, live parameter catalog
(`list_sweep_recipes`) for every built-in strategy. A hand-maintained
second list would drift out of sync with that immediately — the same
mistake Step 04 avoided by not building a parallel strategy catalog.
`rules.yaml` now holds only `parameter_library`: generic knowledge about
what a *kind* of parameter (a moving-average period, an oscillator
threshold, ...) tends to need as a starting search window, independent of
which strategy it belongs to.

### Two ways a candidate's code gets produced

Match Step 06's `run_sweep_candidate` tool's two modes:
- **Recipe mode** — an existing built-in strategy template. Call
  `list_sweep_recipes` first to see its real parameter names and defaults
  — do not guess them.
- **Base-code mode** — an existing strategy's actual source (e.g. an
  LLM-generated candidate from a prior research iteration). Vary one
  named parameter at a time via `param_name`/`param_value`.

### Classifying a parameter into the library

`list_sweep_recipes`/an existing strategy's code gives you a parameter's
*name*, not its *type*. Classify by what the name and context suggest,
against `parameter_library`'s entries — this is a judgment call, not a
lookup table:
- Names like `fast_period`, `slow_period`, `hull_period`, `lookback`,
  `vwap_period` → `moving_average_period`.
- Names like `rsi_period`'s companion thresholds (`oversold`,
  `overbought`), `adx_threshold` → `oscillator_threshold` (bounded,
  roughly 0-100 scale).
- Names like `bb_std`, `zscore_entry`, `st_multiplier`, `vol_entry` →
  `atr_multiplier`-style (a multiplier on a volatility measure) — check
  the recipe's description in `list_sweep_recipes` to confirm it's a
  multiplier, not a raw threshold, before classifying it there vs.
  `signal_threshold`.
- Names like `roc_threshold` → `signal_threshold` (small-magnitude raw
  ratios).
If nothing fits, say so explicitly and propose a sane seed step/bounds
from first principles — don't force a bad classification just to reuse an
existing type.

### The adaptive search algorithm

1. Identify the strategy (recipe key or base code) and its parameters via
   `list_sweep_recipes` or by reading the base code directly.
2. Classify each parameter you intend to vary (see above) and resolve its
   `param_type` against `parameter_library` for a starting `seed_step` and
   `seed_bounds_pm`. These are a reasonable first guess, not the final
   search space.
3. **Before running anything**, call `create_hypothesis` with your
   expectation for this parameter — e.g. "fast_period around 9-15 should
   show a clear sensitivity peak; slow_period at ±5 around 50 probably
   won't, since 50-period averages typically need a much wider window."
   Keep the returned `hypothesis_id` for this parameter's search.
4. Run a **coarse pass**: call `run_sweep_candidate` at each seed-step
   point across the seed bounds, holding other parameters at their
   default. Read back `metrics.sharpe_ratio` and `validation` from each.
5. Judge sensitivity per parameter from the coarse pass:
   - **Low sensitivity** (the objective barely moves across the whole
     window, or keeps improving monotonically toward one edge) → the
     window is probably wrong, not the parameter. Widen `seed_bounds_pm`
     outward (`defaults.widen_bounds_by_steps` more steps past whichever
     edge kept improving) and re-run the coarse pass there.
   - **High sensitivity** (a visible peak between adjacent coarse points)
     → narrow the step (`defaults.refine_step_factor` × the seed step)
     and re-run around the best coarse point(s) to refine it.
   - **No sensitivity even after widening** → the parameter isn't doing
     useful work for this strategy/symbol; fix it at its default and stop
     searching that dimension.
6. Call `add_hypothesis_evidence` against this parameter's
   `hypothesis_id` with what actually happened (`metric="sharpe_ratio"`,
   the observed value, `conclusion` "supports" or "contradicts" your
   step-3 expectation, and why) — every widen/narrow decision gets its
   own hypothesis-then-evidence pair, not one hypothesis for the whole
   search.
7. Repeat steps 3-6 (widen or narrow, per parameter, independently) until
   Step 08's governor says stop — this skill does not define its own
   stopping condition; see `governor` (paired design, same round-by-round
   loop).
8. **Evaluate every candidate produced along the way against ALL of
   `gatekeepers/rules.yaml`'s `candidate_evaluation` entries** — there is
   no per-strategy subset to select; every check applies to every
   candidate uniformly. Fetch what you need via `get_backtest_validation`
   (statistical verdict, metrics, trade count) for the same `run_id`
   `run_sweep_candidate` returned. Converge on the best candidate that
   passes every `hard` check. If none pass, report that clearly — never
   silently return a gatekeeper-failing result as "the best one."

**Worked example — parameter sensitivity** (the SMA9/SMA200 case this
skill was originally written around, now grounded in real tool calls): a
`crossover`-recipe candidate exposes `fast_period` (default 20) and
`slow_period` (default 50) — both classify as `moving_average_period`.
`create_hypothesis("fast_period should peak near a shorter window")`, then
a coarse pass via `run_sweep_candidate(recipe="crossover", params={...})`
at `fast_period` values 15/20/25 (seed step 1... wait, actually run
several points spanning `seed_bounds_pm=5`) shows a clear peak — narrow
the step and refine around it, then `add_hypothesis_evidence` confirming
the expectation. A parallel coarse pass on `slow_period` at ±5 around 50
shows almost no change — that's a signal the window is too narrow for a
50-period average to matter, not that the parameter is useless. Widen
`slow_period`'s bounds well past ±5 (e.g. ±30) and re-run there before
`add_hypothesis_evidence` records whatever the wider pass actually shows.

**Worked example — strategy-alignment fallback:** a `rsi`-recipe candidate
on a trending symbol keeps failing `gatekeepers`' `is_oos_sharpe_floor`
check even after several widen/narrow rounds on `rsi_period` — no
sensitivity, still failing. Rather than giving up or blindly trying
unrelated recipes, load `strategy-tags/tags.yaml`. `rsi_mean_reversion`
(the registered strategy this recipe most resembles) is tagged
`regime: [ranging, mean_reverting]` — and you're on a *trending* symbol.
That's the actual answer: this isn't a parameter problem, it's a
regime mismatch — an RSI mean-reversion approach isn't suited to a
trending symbol at all. Check `tags.yaml` for a strategy tagged
`regime: [trending]` instead — `adx_filtered_crossover` or `ma_crossover`
are candidates. **Bridging note:** `strategy-tags` describes strategies
registered in `vinu-strategy` (a different execution format — a
declarative pipeline, not `run_sweep_candidate`-style Python). Where a
recipe key matches by name (`adx_filtered_crossover` exists as both a
`vinu-strategy` registered strategy and a Step 06 recipe key — check
`list_sweep_recipes`), switch directly to sweeping that recipe. Where no
recipe matches, the tag is directional guidance for what kind of approach
to try next (e.g. informing a new base-code candidate), not a literal
recipe to plug in — don't pretend the translation is automatic when it
isn't.

### Primary objective

Unless told otherwise, rank passing candidates by `metrics.sharpe_ratio`
descending, then by `metrics.max_drawdown` ascending (closer to zero) as
a tiebreaker — both real fields on every `run_sweep_candidate`/
`get_backtest_validation` response.
