---
name: 07-optimizer-rules-skill
status: Done
phase: 3
code: B4
depends_on: [03-gatekeepers-skill, 06-parameter-sweep-engine, 04-strategy-tag-layer]
unlocks: []
---

# Step 07 — Optimizer-Rules Skill (adaptive search, self-directed)

## Why this step

This is where Focus 1 becomes real reasoning instead of a mechanism. Its
design already went through one major correction in this plan's history:
the first draft was a numbered procedure (coarse pass → check sensitivity →
widen/narrow → repeat) that was, correctly, called out as still too much
like a script for the agent to merely execute rather than reason through.
The corrected version treats `rules.yaml` as a **parameter-type knowledge
library** (what a `moving_average_period` parameter tends to need as a
starting step, what an `oscillator_threshold` tends to need — generic,
reusable across strategies) and `SKILL.md` as **reasoning principles**, not
a script: the agent decides, each round, whether a parameter needs a wider
window or a finer step, based on what it actually observed.

## What we're achieving

The `SKILL.md` and `rules.yaml` already drafted in
`project-understanding/skills/optimizer-rules/` (parameter-type library:
`moving_average_period`, `oscillator_threshold`, `ratio_threshold`,
`atr_multiplier`, `signal_threshold` — each with a seed step/bounds and
reasoning notes) are close to right and mostly need to be re-pointed at
real infrastructure: Step 06's engine for running candidates, Step 03's
gatekeepers for judging them, and Step 04's tags for the "does another
strategy align" fallback when a strategy isn't working.

## Where it matters in the future

This is Focus 1's deliverable. When this step is done, a user can say
"I've added this strategy" and the agent should be able to plan its own
investigation: pick tickers, run an initial test via Step 06, judge it via
Step 03, and — if it's not working — check Step 04's tags for something
aligned before giving up, all without a human writing the search plan by
hand each time.

## How it connects to other steps

- **Depends on Step 06** — nothing to drive without the sweep engine
  existing.
- **Depends on Step 03** — nothing to judge candidates against without the
  real gatekeepers interface.
- **Depends on Step 04** — the "does another strategy align" fallback
  needs tags to filter on; without them this degenerates into "give up" or
  "re-read every strategy," both bad.
- **Paired with Step 08** — the governor (hard limit + progress heuristic +
  expectancy heuristic) is what stops this loop; design them together, not
  in isolation. A search algorithm and its stopping condition are one
  design, not two.
- **Should write hypothesis/evidence through Step 02's tools** — every
  round's expectation-before-seeing-the-result should be recorded via the
  `HypothesisRegistry`/`Evidence` mechanism Step 02 exposes, not a new,
  parallel log. This is what makes "was my conclusion correct"
  answerable later.

## Substeps

1. Re-read the current drafts of `project-understanding/skills/optimizer-rules/SKILL.md`
   and `rules.yaml` — they already encode the adaptive coarse→fine,
   widen-if-flat/narrow-if-peaked algorithm and the parameter-type library.
   Confirm they still make sense given everything learned since (real
   `vinu-strategy` registry, real gatekeepers).
2. Replace every reference to a placeholder tool call with the real tool
   names from Step 06 (run one candidate) and Step 03 (judge a candidate).
3. Add the explicit hypothesis-logging behavior: before running a coarse
   pass or a widen/narrow decision, the agent should record its expectation
   and reasoning via Step 02's hypothesis-registry tool, so it's checkable
   against the outcome afterward.
4. Add the "does another strategy align" fallback behavior, referencing
   Step 04's tags directly (e.g. "same regime + shared indicator ⇒
   candidate").
5. Write the worked example already present in the current draft (the
   SMA9/SMA200 sensitivity case) — keep it, it's a good concrete anchor —
   and add a second worked example covering the "strategy isn't working,
   check alignment" branch, since the current draft only covers the
   parameter-search branch.

## What was actually built

**A gap surfaced immediately on substep 3: Step 02 never built a write
tool for hypotheses**, only the read-only `query_hypotheses`. Every
`HypothesisRegistry` write in the existing codebase happens automatically
inside `StrategyResearchLoop.run()` — but Step 06's sweep engine calls
`ResearchTools.run_backtest` directly, bypassing `run()` entirely, so
nothing writes hypotheses/evidence for sweep candidates at all. This
step's own Definition of Done requires hypothesis-logging to be real, not
aspirational, so two new mutating routes and two new tools were built as
part of this step (matching the plan's own recurring principle —
"knowledge without reach is not knowledge the agent can act on," first
stated in Step 02):
- `vinu_research/server/routes_hypothesis.py` — `POST /research/hypotheses`
  (create), `POST /research/hypotheses/{id}/evidence` (add evidence).
  Deliberately separate from `routes_introspect.py` (read-only), matching
  the codebase's own existing split (`routes_broker.py`'s mutating routes
  vs. read-only ones).
- `vinu_agent/tools/hypothesis_write_tools.py` — `create_hypothesis`,
  `add_hypothesis_evidence` (both `is_readonly=False`).
- Wired into `app.py`; 4 new route tests + 8 new tool tests, all passing;
  confirmed both tools auto-discovered by `build_registry()`.

**A second, larger correction: the draft's `strategies:` section in
`rules.yaml` was removed entirely**, not just re-pointed. Its three
example strategies (`hurst_regime`, `adaptive_vwap_mean_reversion`,
`hull_ma_slope_rider`) matched neither the real `vinu-strategy` registry
(Step 04 confirmed only 4 real strategies exist, none of these three among
them) nor Step 06's 15 real `BUILTIN_RECIPES`. More importantly, Step 06's
`list_sweep_recipes` tool already exposes a live, real parameter catalog
per recipe — maintaining a hand-written duplicate would drift immediately,
the exact mistake Step 04 already avoided for the strategy-tags layer.
`rules.yaml` now holds only `parameter_library` (the generic,
strategy-independent parameter-type knowledge), with `seen_in_recipes`
cross-references added per type — checked against all 15 real recipes'
actual parameter names (`TEMPLATE_METADATA`), not guessed.

**Parameter-type classification is now an explicit reasoning step in
`SKILL.md`** ("Classifying a parameter" section) — since there's no
`strategies:` lookup table anymore, the agent classifies a real
parameter's name into a `parameter_library` type by pattern (documented
with real examples from real recipe names), same adaptive-reasoning
posture as the coarse-to-fine search itself, not a second script.

**Gatekeeper application corrected:** the draft assumed each strategy
declares its own `gatekeepers_required` subset. Step 03's actual design
has no such per-strategy opt-in — every `candidate_evaluation` check
applies to every candidate uniformly. `SKILL.md` states this directly.

**Real field names corrected:** `sharpe_oos`/`maxdd_oos` (placeholders,
never real) replaced with `metrics.sharpe_ratio`/`metrics.max_drawdown` —
confirmed against `BacktestMetrics`'s actual dataclass fields.

**Both worked examples added** (substep 5): the SMA9/SMA200 sensitivity
case (kept, now using real tool calls throughout) and a new
strategy-alignment-fallback case (RSI mean-reversion failing on a trending
symbol → `strategy-tags` reveals it's a regime mismatch, not a parameter
problem → redirect to a trend-following alternative). The fallback example
also documents a real cross-system nuance found while writing it:
`strategy-tags` describes `vinu-strategy`-registered strategies (a
different execution format from Step 06's recipes/base-code) — where a
recipe name matches a registered strategy name (`adx_filtered_crossover`
exists as both), the bridge is direct; otherwise the tag is directional
guidance, not a literal recipe to plug in. Documented honestly rather than
implying a seamless translation that doesn't exist.

## Definition of done

- [x] `SKILL.md` references only real tool calls from Steps 02
      (`query_hypotheses`, `create_hypothesis`, `add_hypothesis_evidence`
      — the latter two newly built this step), 03 (gatekeepers skill,
      referenced by its real `candidate_evaluation` structure), and 06
      (`run_sweep_candidate`, `list_sweep_recipes`).
- [x] Hypothesis-logging behavior explicit, tied to real tools — including
      the two new ones this step had to build to make the requirement
      possible at all, not just documented.
- [x] Strategy-alignment fallback explicit, tied to Step 04's
      `strategy-tags` skill, including the honest cross-system caveat.
- [x] Two worked examples present: parameter-sensitivity case (updated to
      real tool calls) and strategy-alignment-fallback case (new).
