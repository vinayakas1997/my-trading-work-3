# S-07: A Goal Object With Budgets and a Compliance Guardrail

## What It Is

`03-reference-patterns.md` (Pattern 1C / Phase 3 roadmap) already flags "goal-driven
criteria termination" as a Layer 7 item, but the sketch there is thin. Vibe-Trading's
actual `GoalRecord` (`agent/src/goal/models.py:41-62`) is worth looking at directly
because it's richer than the existing sketch in two specific ways:

1. **Real resource budgets**, not just a target: `token_budget/tokens_used`,
   `turn_budget/turns_used`, `time_budget_seconds/time_used_seconds`, with
   dedicated statuses `BUDGET_LIMITED`, `USAGE_LIMITED` (`models.py:10-24`) that
   are distinct from "the strategy failed" — a goal can stop *because it ran out
   of resources*, tracked and reported separately from "the research concluded."
2. **A `RiskTier` enum** (`RESEARCH_GENERAL` → `LIVE_TRADING_OR_EXECUTION`,
   `models.py:27-33`) plus a hard compliance guardrail: `policy.py:36-48` rejects
   any goal objective that pattern-matches live-order-execution language (English
   *and* Chinese patterns) before the goal is even allowed to start.

## Why It's Required

`vinu_research` currently has exactly one budget knob: `max_iterations`. There's no
tracking of how many LLM calls or how much wall-clock time a run actually consumed
— which matters a lot now, because P2/P4 turned each iteration into up to 6 LLM
calls instead of 2-3. You have no visibility into whether a given run's cost is
proportional to its value. Separately: this loop is described in `00-vision.md` as
strictly research-only ("Live-Trading... Zero LLM calls"), which is exactly the
invariant a `RiskTier`-style guardrail would make structurally enforced rather than
just documented — right now nothing in code stops a `user_idea` string from
containing something like "place a live order for..." and the LLM dutifully
engaging with it in its reasoning, even if nothing downstream actually executes a
trade.

## Impact

- **If unfixed:** no cost accounting per run (can't answer "is this symbol worth
  re-researching, given what the last 5 attempts cost"), and the research/live
  boundary is an architectural convention, not something enforced in code.
- **If fixed:** every run reports its actual resource cost (pairs with S-05's trace
  log for the raw numbers), and the research-only invariant becomes a guardrail
  that fails loudly if violated instead of just being true by construction today.

## How to Use Effectively

1. Start minimal: add `llm_calls_used`, `llm_calls_budget` (not token-level yet —
   too fine-grained to be worth it before S-05's trace log exists to measure
   tokens accurately) to a simple wrapper around `StrategyResearchLoop.run()`, and
   have it refuse to start a new iteration once the budget is spent, ending with a
   `BUDGET_LIMITED`-equivalent status distinct from your existing `STOP`/`PASS`.
2. The compliance-guardrail piece is worth adding even in the current research-
   only state, as a cheap early-warning: a simple regex/keyword check on
   `user_idea` in `service.py.run_research()` that logs (not blocks, initially) if
   it looks like live-execution language ("place order", "execute trade", "buy N
   shares now") — this becomes a hard block later if/when a live-execution path is
   ever added (see **S-12**), and costs almost nothing to add now.
3. Don't conflate `Goal` with `Hypothesis` — they answer different questions
   (`Goal`: "how much budget did *this run* cost and why did it stop"; `Hypothesis`:
   "what do we believe about this symbol across *all* runs"). Keep them as separate
   objects even if `Goal` starts out very small.

## Implementation Hint — Where This Fits Today

**Important discovery: a `Goal` dataclass already exists and is already used — just
not for budgets, and not connected to the main research loop.**

- `models.py:~65`: `Goal(goal_id, hypothesis_id, objective, criteria: list[str],
  status: str = "pending")` — already defined.
- `tools.py:301-336`'s `run_autopilot(hypothesis_id, registry)` already
  constructs one: takes a `Hypothesis`, builds a `Goal` with hardcoded criteria
  (`"Sharpe ratio > 1.0"`, `"Max drawdown > -20%"`, `"Win rate > 40%"`,
  `tools.py:318-322`), and returns it as a dict. It's invoked from a standalone
  CLI command (`cli.py:365-390`, `vinu-research autopilot <hypothesis_id>`).
- **The catch, same shape as S-02's discovery:** this `Goal` is never persisted
  (no `GoalStore`, it's built and returned/printed, then gone), has no budget
  fields (`token_budget`, `turn_budget`, `time_budget_seconds`), no `RiskTier`,
  and — critically — `StrategyResearchLoop.run()` (the actual LLM research loop)
  never creates, reads, or updates a `Goal` at all. The autopilot pathway and the
  main research pathway are two separate, disconnected systems that happen to
  share the same `HypothesisRegistry`.

**What this means for implementation:** don't design `Goal`'s budget/RiskTier
fields as a brand-new addition to `models.py` — extend the *existing* `Goal`
dataclass in place (add `token_budget`, `tokens_used`, `risk_tier`, etc. as new
optional fields, same pattern R-A used to extend `Hypothesis`). The harder, more
valuable part of this suggestion isn't the dataclass — it's wiring `Goal` into
`StrategyResearchLoop.run()` for the first time, since today nothing in the main
loop touches `Goal` at all, even though the type already exists.

**Compliance-guardrail entry point:** `service.py:58-70`, the very top of
`run_research()`, where `user_idea` and `symbol` first arrive — before `record`
is even constructed. Cheapest possible placement, no dependency on the `Goal`
work above.

## Potential Bugs to Watch For While Testing

- **Regex guardrail false positives on ordinary research language.** A naive
  pattern for "live execution language" can trip on completely normal research
  ideas — `"buy-the-dip momentum strategy"` or `"execute a mean-reversion
  backtest"` both contain words a careless regex would flag. Test with a batch
  of realistic, legitimate `user_idea` strings (not just the obvious violation
  case) before trusting the pattern in anything stricter than log-only mode.
- **Extending `Goal` must not break the existing autopilot construction call.**
  `tools.py:314-324` constructs `Goal(goal_id=..., hypothesis_id=..., objective=...,
  criteria=..., status="active")` using keyword args today — adding new fields
  with defaults is safe for this call site, but test it explicitly (run the
  existing `autopilot` CLI command) after the change, since it's easy to touch
  `models.py` and only think about the *new* call site, not the one that already
  exists and already works.
- **Concurrent budget-counter updates under `asyncio.gather`.** If
  `tokens_used`/`llm_calls_used` is incremented per LLM call, and multiple
  candidate-generation calls run concurrently via `asyncio.gather` (as
  `llm_generator.py`'s `generate()` already does for `n_candidates`), a naive
  `goal.tokens_used += n` from multiple coroutines can lose updates (read-modify-
  write race even within a single process, no threads needed — just interleaved
  coroutines). Test with `n_candidates > 1` and confirm the final count matches
  the actual number of calls made, not less.
