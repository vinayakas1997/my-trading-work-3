# S-06: Context/Budget Management With a Guaranteed Graceful Stop

## What It Is

The loop today stops on one of: an explicit verdict (`PASS`/`STOP`), a pivot
decision from `_reflect()`, a drawdown breach, "not improving" detection, or
simply running out of `max_iterations`. There's no notion of a *budget* being
tracked (tokens, LLM calls, wall-clock time) and no guaranteed "wrap up gracefully"
step — if the loop is going to hit `max_iterations` without a clean PASS/STOP, it
just... stops, whatever state it's in.

Vibe-Trading's `loop.py:637-975` layers this explicitly:
- Compaction thresholds at 50% (`_microcompact`), 70% (`_context_collapse`), and
  100% (`_auto_compact`) of the token budget (`loop.py:658-675`).
- A "wrap-up nudge" injected at 80% of `max_iterations` (`loop.py:634,684-694`) —
  the agent is told explicitly it's running low on budget, so its next decisions
  bias toward concluding rather than opening new lines of exploration.
- A forced text-only final iteration (tool definitions dropped,
  `loop.py:726-729`) that guarantees the loop always terminates with an actual
  answer, not a truncated mid-thought.

## Why It's Required

P4's `_reflect()` can already end a run early (pivot/stop) based on a single LLM
judgment call after just iteration 2 — so your loop already has *unpredictable*
early termination. What it doesn't have is *predictable* termination: nothing
currently tells the LLM "you're about to run out of iterations, wrap up" before
`max_iterations` is hit, so the failure mode is silent truncation rather than a
deliberate, LLM-aware conclusion.

## Impact

- **If unfixed:** runs that don't reach PASS/STOP by `max_iterations` just stop —
  the last iteration is whatever was mid-refinement, not a considered "here's my
  best attempt and why" conclusion.
- **If fixed:** every run ends with an intentional wrap-up, which also gives you a
  natural place to write a final summary into the hypothesis's evidence (S-02) and
  memory context (S-04) instead of leaving the run's ending implicit.

## How to Use Effectively

1. Add an iteration-budget nudge: at `iteration >= 0.8 * max_iterations`, inject a
   note into the next generation/refinement prompt: "You have N iterations left —
   if nothing has passed yet, converge on your best attempt rather than trying a
   new approach." This is cheap (one string, no new infra) and directly
   complements `_reflect()`'s pivot logic — right now pivot and budget-awareness
   don't talk to each other at all.
2. Token/LLM-call budgeting is a bigger lift (needs the trace log from **S-05** to
   even measure it) — treat that as a later phase, not part of the first cut here.
3. Don't copy Vibe-Trading's multi-stage compaction (`microcompact`/
   `context_collapse`/`auto_compact`) wholesale — that's solving a chat-context-
   window problem for a long-running conversational agent, which is a different
   shape of problem than your bounded N-iteration research loop. The piece worth
   taking is the *principle* (nudge before the limit, force a clean stop at the
   limit), not the specific 3-stage mechanism.

## Implementation Hint — Where This Fits Today

**Entry point:** `loop.py`'s `_default_quant_coder()` (~`loop.py:977` onward) —
the same function P1/P2 already extended to inject `memory_context` and
`stock_profile` into the `story` dict (`loop.py:963-985`, the
`story["memory_context"] = mem` / `story["stock_profile"] = sp` lines).

**Why this is feasible right now:** the injection mechanism this suggestion needs
already exists and is already the established pattern — P1 and P2 both added
exactly this shape of change (compute a string, stick it on `story[key]`, let
`llm_generator.py`'s prompt builders pick it up). A budget nudge is:
```python
if iteration >= 0.8 * self._config.max_iterations:
    story["budget_note"] = (
        f"Only {self._config.max_iterations - iteration} iteration(s) remain — "
        "converge on your best attempt rather than starting a new approach."
    )
```
placed right alongside the existing `mem`/`sp` block, plus one new `if
memory_context:` — style line in `_build_generation_prompt`/
`_build_refinement_prompt` (`llm_generator.py`) to append it. This is the same
3-part pattern (compute → story dict → prompt builder appends) already used twice
in this file; it is not a new integration pattern.

**`self._config.max_iterations`** (`config.py:46`, `DEFAULT_MAX_ITERATIONS`) is
already the loop's only budget concept today — this suggestion doesn't require
adding a new budget type, just reacting to the existing one earlier than "stop at
the boundary."

## Potential Bugs to Watch For While Testing

- **Off-by-one with small `max_iterations`.** `0.8 * max_iterations` with
  `max_iterations=3` gives `2.4` — `iteration >= 2.4` only ever fires on
  iteration 3, the *last* one, leaving no room for the nudge to actually change
  behavior before the loop ends. Test with small `max_iterations` values (2, 3 —
  realistic for a fast/cheap config) specifically, not just the default, since
  the nudge can be a no-op exactly when iteration budgets are tightest.
- **Guard the `story is None` case for the new field, same as the existing
  ones.** `_default_quant_coder()`'s `story` starts as `None` and is only
  initialized inside each `if` block that needs it (see the `mem`/`sp` pattern at
  `loop.py:993-1004`) — a new `budget_note` block must include its own `if story
  is None: story = {}` guard or it will `AttributeError` on `None["budget_note"]
  = ...` whenever `_angle_context`/`memory_context`/`stock_profile` are all
  empty. Test the case where the budget nudge is the *only* thing populating
  `story` for that iteration.
- **Contradictory signals with `_reflect()`.** Both this nudge and `_reflect()`
  can become active near the end of a run (`_reflect()` triggers as early as
  iteration 2 on low sharpe; the 80% nudge triggers near `max_iterations`). Test
  a run where both conditions are true in the same iteration and confirm the
  prompt doesn't tell the LLM to both "pivot to something new" and "converge on
  your current attempt" simultaneously — that's a real prompt-contradiction risk
  worth an explicit test case, not just each one tested in isolation.
