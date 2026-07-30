---
name: governor
description: Two-layer stopping logic for optimizer-rules' adaptive sweep loop — hard limits that guarantee termination, plus two adaptive heuristics (progress, expectancy) that can disagree. Paired with optimizer-rules, not standalone.
category: tool
---

## Governor — When to Stop the Sweep Loop

This skill is not standalone — it's the stopping logic for
`optimizer-rules`' round-by-round adaptive search (Step 3 in that skill's
"adaptive search algorithm" loop, steps 3-6, repeated per parameter). Read
`optimizer-rules/SKILL.md` first; this document only makes sense alongside
it.

### Layer 1 — hard limits (never bend)

The sweep loop runs inside the agent's own ReAct loop
(`vinu_agent/agent/loop.py`) — **not** `vinu_research/loop.py`'s
`StrategyResearchLoop.run()`, a different, same-named file for a
different, existing loop. Every `run_sweep_candidate`/
`create_hypothesis`/`add_hypothesis_evidence` call this skill makes is one
iteration of that ReAct loop, confirmed real in code
(`vinu_agent/agent/loop.py:41`, `max_iterations: int = 50`, enforced by
`while iteration < self.max_iterations`). There is no separate `Goal`-
object LLM-call/wall-clock budget wired into this path (that mechanism —
`_check_goal_budget` — belongs to `vinu_research/loop.py`'s different
loop) — so **the 50-iteration ReAct cap is the only real hard limit
backing this search today.** Max tool calls and max iterations are the
same number here, not two independent limits.

**The wrap-up nudge changes the actual deadline.** The ReAct loop already
sends a system message at 80% of the budget consumed (confirmed in code:
`vinu_agent/agent/loop.py:79-90`) telling the agent to wrap up and make
*no further tool calls*. This means any resumability action — recording
the current hypothesis/evidence state — must happen **before** that
nudge, not after. Treat 80% of `max_iterations` (i.e. iteration 40 of 50)
as the real hard deadline for this skill's own bookkeeping, not iteration
50 itself.

**Resumability — corrected from this step's original assumption.** The
plan originally assumed Step 02's `get_run_checkpoints`/
`iteration_checkpoints` mechanism would back multi-session resumability
here. It doesn't apply: that table is written only by
`StrategyResearchLoop.run()` (a different loop, confirmed by reading
`vinu_research/loop.py` in full — `save_checkpoint` is called nowhere in
the sweep engine). The sweep loop's real resumable state is the
**hypothesis/evidence trail Step 07 already writes every round** — call
`query_hypotheses(symbol=...)` at the start of a new session to
reconstruct which parameters were already tried, their best values, and
whether each expectation was confirmed, before deciding where to resume.
No new storage mechanism is needed; the one Step 07 built for a different
reason already serves this purpose.

### Layer 2 — adaptive heuristics (can disagree with each other)

**Progress heuristic.** `vinu_research/loop.py::_is_improving()` looks
like a ready-made version of this but **cannot literally be extended** —
it lives in, and is only called from, `StrategyResearchLoop.run()`, which
the sweep loop never touches. Its *logic* is still the right starting
point (compare current round's objective to the previous round's), scaled
from a single-round check to an N-round-flat window: **stop searching a
given parameter after `stop_if_no_improvement_for` (default 5, see
`rules.yaml`) consecutive rounds where `metrics.sharpe_ratio` didn't
improve by more than `optimizer-rules/rules.yaml`'s `refine_step_factor`-
scaled threshold.** Read this directly off the evidence trail
`add_hypothesis_evidence` already recorded — no new storage, just
comparing the last N recorded values for this parameter's hypothesis_id.

**Expectancy heuristic.** Computed the same way trading expectancy is
computed, applied to search *rounds* instead of trades:

```
EV = win_rate × avg_win − loss_rate × avg_loss
```

- A **round** = one coarse-pass point or one widen/narrow attempt for a
  parameter.
- A round **wins** if `metrics.sharpe_ratio` improved over the
  best-so-far for that parameter; **loses** otherwise.
- `win_rate`/`loss_rate`: fraction of rounds so far (in this session,
  across all parameters searched) that won/lost.
- `avg_win`: mean sharpe improvement magnitude on winning rounds.
- `avg_loss`: mean sharpe decline (or zero-improvement gap) magnitude on
  losing rounds.
- **Continue if EV > 0**, even through a losing streak — a losing streak
  does not by itself justify stopping if the payoff asymmetry still
  favors continuing.

**Worked example** (the case that originally motivated this layer): three
consecutive rounds each show a small decline of -0.05 sharpe (three
losses). A fourth round, if tried, would show +0.40 (a win) — but you
don't know that yet; the decision has to be made after round 3, from the
session's win/loss history so far. Suppose this session's accumulated
win_rate is 30% (0.3) and loss_rate 70% (0.7), with avg_win 0.40 and
avg_loss 0.05 (consistent with what's been observed across parameters
this session): `EV = 0.3×0.40 − 0.7×0.05 = 0.12 − 0.035 = +0.085`. EV is
positive — continue despite the three-loss streak. This is exactly the
"3 losses, but a 4th win big enough to still be net profitable" case,
made operational: the decision doesn't require seeing round 4, only an
honest EV estimate from what's already been observed.

### When the two heuristics disagree

This is where most of this design's actual value is — the rule is
deliberately asymmetric, not "whichever wins":

- **Progress stalled, but expectancy still favorable** → continue, but
  only for a bounded number of extra rounds (`expectancy_override_cap`,
  default 3 — see `rules.yaml`), then stop regardless of what expectancy
  says. Expectancy justifies patience, not indefinite continuation — an
  unbounded override would let Layer 2 quietly defeat its own "progress
  stalled" signal forever.
- **Progress still fine, but expectancy turned unfavorable** (EV ≤ 0
  despite recent improvement — e.g. gains are shrinking relative to
  accumulating risk/cost) → **stop anyway.** "Still improving" doesn't
  mean "still worth pursuing." This is the more decisive case: expectancy
  going negative is treated as authoritative for stopping, even when
  progress alone would say keep going. Chasing diminishing returns
  because a metric is still technically ticking up is the exact failure
  mode this heuristic exists to prevent.
- **Both agree** → no conflict, follow the shared verdict.

Layer 1's hard cap is what actually enforces all of the above if Layer
2's heuristics somehow keep disagreeing productively forever — it is the
backstop, not the primary mechanism.
