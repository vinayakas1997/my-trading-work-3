---
name: 08-governor
status: Not Started
phase: 3
code: B6
depends_on: [01-verification-pass, 02-tool-wiring]
unlocks: []
---

# Step 08 — Governor (stopping and continuation logic)

## Why this step

Without this, "self-directed" becomes "runs forever" — a strategy that
keeps looking "almost promising" could consume unbounded compute chasing
it. This came out of a specific correction during design: a flat "stop
after N failures" rule would actually contradict real trading logic (a
losing streak can still be worth continuing if the payoff asymmetry
justifies it — e.g. 3 losses, but a 4th win big enough to still be net
profitable). The governor needs to reason about that, not just count.

## What we're achieving

Two layers, working together, documented as one coherent design:

- **Layer 1 — hard limits.** Max iterations, max wall-clock, max tool
  calls. Never bend. Their only job: guarantee termination no matter what.
  These must respect the agent's actual ReAct loop cap (confirmed 50
  iterations per session in `agent-self/SKILL.md`) — meaning a long search
  needs to be **resumable across sessions**, using Step 01/02's confirmed
  checkpoint mechanism, not assumed to run uninterrupted in one session.
- **Layer 2 — adaptive heuristics.** Two, and they can disagree:
  - *Progress heuristic* — "is progress still happening" (stop after N
    rounds with no improvement in the primary objective).
  - *Expectancy heuristic* — "is continuing still worth it," computed the
    same way trading expectancy is computed (`EV = win_rate × avg_win −
    loss_rate × avg_loss`), applied to the search process itself, not just
    to trades inside a backtest.

Layer 1 is what stops it if Layer 2's heuristics keep saying "one more"
forever.

## Where it matters in the future

This is what makes Focus 1's search trustworthy rather than a runaway
process, and it's the piece most directly threatened by an unverified
assumption (Step 01's open question about `loop.py`'s actual stop
condition) — this document must not contradict what `loop.py` already
does; it should extend it.

## How it connects to other steps

- **Depends on Step 01** for `loop.py`'s real stop condition — do not
  finalize Layer 1's design until that's confirmed; this governor should
  complement existing behavior, not fight it.
- **Depends on Step 02** for the actual tool that reads checkpoint/
  exhaustion state — Layer 1's resumability claim is only real once that
  tool exists.
- **Paired with Step 07** — this is not a standalone skill; it's designed
  alongside the optimizer-rules skill because the search algorithm and its
  stopping condition are one design split across two files for clarity,
  not two independent designs.

## Substeps

1. Confirm Step 01's finding on `loop.py`'s stop condition before writing
   anything here — if it already implements something equivalent to Layer
   2, document the relationship explicitly rather than re-describing it.
2. Write Layer 1 explicitly bounded by the 50-iteration ReAct cap, with the
   resumability behavior (save/read checkpoint via Step 02's tool) spelled
   out as the mechanism that makes a multi-session search coherent.
3. Write Layer 2's progress heuristic — reuse whatever
   `stop_if_no_improvement_for`-style concept already exists in the current
   `optimizer-rules` draft rather than reinventing it.
4. Write Layer 2's expectancy heuristic with a concrete worked example
   (the "3 losses, 4th trade wins enough to stay net positive" case that
   originally motivated this layer) so it's an operational rule, not an
   abstract principle.
5. Write explicitly what happens when the two heuristics disagree —
   progress stalled but expectancy still favorable, or progress fine but
   expectancy turned unfavorable — since this is where most of this
   design's actual value is.

## Open risks / assumptions

- Entirely dependent on Step 01's `loop.py` finding — do not treat this as
  startable before that's answered.

## Definition of done

- [ ] Layer 1 explicitly reconciled with `loop.py`'s real stop condition.
- [ ] Layer 1's resumability tied to a real Step 02 tool call.
- [ ] Layer 2's two heuristics both have a concrete worked example.
- [ ] The disagreement-resolution rule between the two heuristics is
      written down, not left implicit.
