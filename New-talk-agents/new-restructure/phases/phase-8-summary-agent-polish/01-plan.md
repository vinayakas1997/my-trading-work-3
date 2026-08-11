---
name: phase-8-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 8 -- fully independent enhancement to the Summary Agent. Wires the existing, unused Calibration Tracker in, and adds a genuinely new cross-angle consensus check. No dependency on any other phase.
---

# Phase 8 -- Summary Agent polish

## Why this phase has no dependencies

Nothing else in the 9-phase build order reads from or writes to what this
phase changes -- it upgrades the Summary Agent's own output quality, one
level upstream of everything else, without changing any interface another
phase depends on. Can be built any time, in parallel with anything else.

## What exists today, confirmed real

- `teams/screener/agents/angle_synthesizer/prompt.md`: calls
  `get_all_angles(ticker)` once, reports how many of the ~31 angles have
  real data, cites specific numbers from the ones that do. Lists angles
  **individually** -- confirmed by reading the real prompt -- it does not
  cross-check them against each other.
- Grounding discipline already in place: "only treat an angle as
  informative if `row_count > 0`," never invent a number. This is why the
  team survived a real-LLM test where most angles had no data yet -- it
  said so plainly instead of padding a confident summary. Both additions
  below must preserve this discipline, not work around it.
- `vinu-research/calibration.py`'s `CalibrationTracker`/`CalibrationGate`
  -- built, tested, currently unused anywhere.

## Two additions, genuinely different questions -- don't conflate them

**1. Calibration Tracker wiring -- "has this method been right *over
time*."** Feeds the Summary Agent which angles to actually trust right
now, based on each angle's own historical forecast accuracy. Call target
depends on the state of the separate `vinu-research` in-process migration
at the time this phase is built: if migrated by then, an in-process
import; if not yet, the existing HTTP path to `research-api`. Confirm
current migration state before implementing -- don't hardcode against
whichever was true when this plan was written.

**2. Cross-angle consensus check -- "do independent methods agree *right
now*."** New capability: given two or more angles that produce comparable
output for the same ticker (e.g. `arima` vs. `chronos` forecast
direction, `regime_analysis` vs. `trend_lifecycle` characterization),
report whether they agree or diverge, as part of the Summary Agent's
output.

**Agreement needs a precise, per-angle-pair-type definition, not a vague
"do they agree."** Different angle types need different comparison rules:
- **Directional angles** (forecast up/down): compare sign.
- **Magnitude angles** (a numeric forecast value): compare relative
  distance against a stated tolerance, not exact equality.
- **Categorical angles** (regime label, lifecycle stage): compare
  exact-match or a stated adjacency rule (e.g. "high_vol" and
  "transitioning" might count as adjacent, "bull" and "high_vol" would
  not) -- this adjacency table needs to be written explicitly, not left
  to LLM judgment call by call, or the same two angles could be scored as
  "agreeing" one day and "diverging" the next with no code change.

**This sits upstream of everything else on purpose.** Fixing consensus
detection once here strengthens every downstream stage without any of
them needing to re-derive it -- same reasoning as why the grounding
discipline itself lives here rather than being re-implemented per angle
consumer.
