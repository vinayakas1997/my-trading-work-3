---
name: 07-optimizer-rules-skill
status: Not Started
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

## Open risks / assumptions

- Fully blocked until 03, 04, and 06 are each individually done — do not
  start substep 2 onward before all three are real.

## Definition of done

- [ ] `SKILL.md` references only real tool calls from Steps 02, 03, 06.
- [ ] Hypothesis-logging behavior explicit, tied to Step 02's registry
      tool, not a new parallel mechanism.
- [ ] Strategy-alignment fallback explicit, tied to Step 04's tags.
- [ ] Two worked examples present: parameter-sensitivity case and
      strategy-alignment-fallback case.
