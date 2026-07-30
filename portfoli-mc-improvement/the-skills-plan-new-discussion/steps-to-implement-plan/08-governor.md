---
name: 08-governor
status: Done
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
  **Resolved by Step 01 (see its Findings §2):** `loop.py` already has a
  hard `max_iterations` cap, an optional `Goal`-based budget
  (`_check_goal_budget` — LLM-call count + wall-clock), an LLM-judgment
  pivot/stop path (`_reflect()`), and — importantly — `_is_improving()`
  (loop.py:934-939), which is **already the progress heuristic** this step
  planned to add, though it's a single-round check (this iteration vs. the
  last), not an N-round-flat window. Layer 2's progress heuristic should
  extend `_is_improving()` to an N-round window, not invent a new,
  parallel one. Checkpoints are saved every iteration but **never read
  back** — grepped the whole file for `resume`/`checkpoint`, only the save
  call exists. Resumability across sessions is genuinely not implemented
  anywhere yet; it has to be built at the orchestration layer (calling
  `get_last_checkpoint()` via Step 02's tool before starting a `run()`),
  not assumed to already exist inside `loop.py`. The expectancy heuristic
  is confirmed genuinely new — nothing like it exists in `loop.py`.
- **Depends on Step 02** for the actual tool that reads checkpoint/
  exhaustion state — Layer 1's resumability claim is only real once that
  tool exists.
- **Paired with Step 07** — this is not a standalone skill; it's designed
  alongside the optimizer-rules skill because the search algorithm and its
  stopping condition are one design split across two files for clarity,
  not two independent designs.

## Substeps

1. ~~Confirm Step 01's finding on `loop.py`'s stop condition~~ — done, see
   Step 01 Findings §2: `_is_improving()` (loop.py:934-939) is the existing
   single-round progress heuristic; checkpoints are write-only (never
   resumed) today.
2. Write Layer 1 explicitly bounded by the 50-iteration ReAct cap, with the
   resumability behavior (save/read checkpoint via Step 02's tool) spelled
   out as the mechanism that makes a multi-session search coherent — this
   is new orchestration-layer logic, not a wire-up of something existing.
3. Write Layer 2's progress heuristic as an explicit extension of
   `_is_improving()` (single-round → N-round-flat window), not a new,
   parallel concept — state the relationship to the existing check plainly.
4. Write Layer 2's expectancy heuristic with a concrete worked example
   (the "3 losses, 4th trade wins enough to stay net positive" case that
   originally motivated this layer) so it's an operational rule, not an
   abstract principle.
5. Write explicitly what happens when the two heuristics disagree —
   progress stalled but expectancy still favorable, or progress fine but
   expectancy turned unfavorable — since this is where most of this
   design's actual value is.

## What was actually built

**Two corrections surfaced immediately, both from checking assumptions
against code that didn't exist when this step was originally planned
(Step 07 hadn't been built yet):**

1. **`_is_improving()` cannot literally be "extended."** It lives in, and
   is only ever called from, `StrategyResearchLoop.run()` — a completely
   different loop from the one this governor controls. The sweep loop
   (Step 06/07) never calls it. Its *logic* (compare this round to the
   last) was kept as the conceptual starting point, scaled to an N-round
   window, but implemented as the agent's own reasoning over the evidence
   trail `add_hypothesis_evidence` already records — not a code edit to
   `vinu_research/loop.py`, which would have zero effect on this loop's
   actual behavior.
2. **Step 02's `get_run_checkpoints`/`iteration_checkpoints` mechanism
   does not back this loop's resumability**, contrary to this step's
   original plan. That table is written only inside
   `StrategyResearchLoop.run()` (confirmed — grepped `save_checkpoint`
   across the sweep engine, zero call sites). The real resumability
   mechanism turned out to already exist for a different reason: Step 07's
   `create_hypothesis`/`add_hypothesis_evidence` writes exactly the state
   a resumed session needs (which parameters were tried, their outcomes,
   whether expectations held) — `query_hypotheses` reconstructs it. No new
   storage needed; documented the existing one as the real mechanism
   instead of inventing a second.

**A third finding, not anticipated in the original plan:** read
`vinu_agent/agent/loop.py` directly (the actual ReAct loop implementation,
distinct from — and easily confused with — `vinu_research/loop.py`, a
naming collision worth flagging the same way the "Monte Carlo" collision
was flagged earlier in this plan). Confirmed `max_iterations: int = 50`
is real, enforced code (`vinu_agent/agent/loop.py:41,67`), and found
something not previously known: a wrap-up nudge fires at 80% of the
budget consumed (`loop.py:79-90`), after which the agent is told to make
no further tool calls. This changes Layer 1's actual deadline — resumable
state must be saved by iteration 40 of 50, not 50 itself. Also confirmed
there is no `Goal`-object wall-clock/LLM-call budget wired into this
path (that belongs to `vinu_research/loop.py`'s different loop) — so the
ReAct 50-iteration cap is the *only* real hard limit here; "max
iterations" and "max tool calls" collapse into one number, not two.

**Files created:**
- `project-understanding/skills/governor/SKILL.md` — Layer 1 (hard cap,
  wrap-up-nudge-aware deadline, hypothesis-trail-based resumability),
  Layer 2 (progress heuristic as N-round evidence comparison; expectancy
  heuristic with the win_rate/avg_win/loss_rate/avg_loss formula and the
  original "3 losses, 4th wins enough" case worked through with real
  numbers), and the disagreement-resolution rule.
- `project-understanding/skills/governor/rules.yaml` — numeric defaults
  (`react_max_iterations: 50`, `wrap_up_at_fraction: 0.8`,
  `stop_if_no_improvement_for: 5`, `ev_continue_threshold: 0.0`,
  `expectancy_override_cap: 3`), validated as parseable YAML.

**Disagreement rule, deliberately asymmetric** (not "whichever heuristic
wins"): a favorable expectancy can justify continuing past a progress
stall, but only for a bounded number of extra rounds
(`expectancy_override_cap`) before the stall reasserts — expectancy
grants patience, not indefinite continuation. An unfavorable expectancy,
conversely, is treated as authoritative for stopping even while progress
still looks fine — "still improving" is not the same as "still worth it,"
which is the exact failure mode this heuristic exists to catch.

## Definition of done

- [x] Layer 1 explicitly reconciled with the *correct* loop's real
      behavior (`vinu_agent/agent/loop.py`, not `vinu_research/loop.py` —
      the original plan's assumption about which stop condition mattered
      here was itself corrected as part of this step).
- [x] Layer 1's resumability tied to a real, existing mechanism —
      Step 07's hypothesis/evidence tools, not Step 02's checkpoint tool
      as originally assumed (corrected, with the reasoning documented).
- [x] Layer 2's two heuristics both have a concrete worked example, the
      expectancy one using the exact motivating case from this step's
      own "why" section, worked through with real numbers.
- [x] The disagreement-resolution rule is written down explicitly, with
      the asymmetry (expectancy-continue is bounded, expectancy-stop is
      authoritative) stated and justified, not left as "whichever wins."
