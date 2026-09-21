# Strategy enhancer

**Status: design-only, not yet implemented.**

## The idea, in one paragraph

Every ticker can have up to 3 candidate trade strategies "in flight" at
once (the K-cap). Right now, when a candidate gets rejected at any point
in the real evaluation chain, that slot doesn't free up — a real bug
found live means the cap counts every candidate a ticker has *ever* had
proposed, forever, with no reset. The fix isn't just "make the cap work
again": once it does, a rejection should actively feed the *next*
candidate — the new idea should know what the other in-flight candidates
already look like (so it doesn't duplicate them) and exactly why the
last one failed (so it doesn't repeat the same mistake). That turns
rejection from a dead end into an input, which is what makes this an
"enhancer" rather than just a bug fix.

## Where this came from

Found live, 2026-09-21, while running a real end-to-end test of the
system (main stack + a local LLM) — not designed up front. Investigating
why a real ticker (AAPL) never got a new trade candidate proposed led to
the K-cap bug, which led to mapping the full real chain a candidate
strategy actually passes through, which led to this idea.

## What's in this folder

- **`00-explanation.md`** — the detailed writeup:
  1. The exact K-cap bug (file/line, real data showing it firing).
  2. The full pre-ACTIVE evaluation chain (7 steps, what each one
     actually checks, LLM vs deterministic).
  3. Which steps' rejection reasons are actually saved anywhere today
     (mixed — some are, some aren't).
  4. **Three more real "hold on degradation" mechanisms**, once a
     strategy is already live — at three different levels (one trade
     plan, one strategy's paper-vs-backtest proof, one strategy's
     ongoing health, and the whole portfolio's real equity) — plus which
     of these already auto-retriggers a new attempt on its own (a real
     precedent to reuse, not reinvent).
  5. Proof that real order placement is structurally unbypassable
     (traced every real caller, not assumed) — and an honest note on
     what's *not* proven unbypassable yet.
  6. A mermaid diagram of the full lifecycle, all levels in one picture.
  7. The proposed enhancer design, broken into a real, ordered build plan.
- **`01-plan.md`** — the concrete implementation plan: a 3-table schema
  (`strategy_evaluation_history` / `_status` / `_step_registry`) in a
  new shared `vinu-infra` module, exactly which real call site in each
  of the 10 steps gets the new write, the real seed data for the step
  registry, both real options for fixing the K-cap bug (with a
  recommendation), the enhancer loop's real trigger/data flow, and a
  dependency-ordered build sequence.

## Current state

Nothing here has been built yet — `01-plan.md` is ready to build from.
The K-cap bug itself is fully understood — see `00-explanation.md`
section 1 and `01-plan.md` section 4. The 3-table schema (`01-plan.md`
section 1) is the natural first real piece, since fixing the cap
properly and building the enhancer loop both depend on it existing.
