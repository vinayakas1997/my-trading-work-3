# S-11: Confidence Scores on Binary LLM Judgment Calls

## What It Is

P4 introduced two binary LLM judgment calls that can meaningfully change a run's
outcome:

- `_reflect()` (`loop.py`): decides `continue`/`pivot`/`stop` as early as
  iteration 2, based on just the last 2 iterations' summaries.
- `_validate_idea()` (`loop.py`): decides whether the user's idea is suitable for
  the stock, logging a warning if not.

Both return a flat decision with no notion of how confident the model was.
fincept-terminal's intent router (`finagent_core/super_agent.py:247-294`) does the
same *kind* of judgment call (classify into one of several options) but emits a
`confidence: 0.0-1.0` alongside the decision and reasoning
(`super_agent.py:35,285,293`), which is then logged and can be used to gate
downstream behavior.

## Why It's Required

A `pivot`/`stop` decision after only iteration 2, based on 2 data points, is
inherently a low-information judgment call — but today it's acted on identically
whether the LLM was very sure or barely guessing. There's no way to distinguish
"this stock is clearly untradeable with these indicators" from "this looks bad but
it's early, I'm not very sure" — both produce the same `pivot`/`stop` string and
the same downstream `break`.

## Impact

- **If unfixed:** you can't calibrate how much to trust early termination —
  `_reflect()`'s aggressiveness (or lack thereof) is fixed by the prompt wording
  alone, with no numeric signal to tune against as you observe outcomes over time.
- **If fixed:** you can set a policy like "only act on `stop` if confidence >
  0.7, otherwise treat as `continue`" — turning a fixed behavior into something
  tunable based on observed accuracy, and giving you a number to actually track
  (via **S-05**'s trace log) to see whether `_reflect()`'s calls are well-
  calibrated over time.

## Impact if paired with logging

Once confidence scores exist and are logged, you can retroactively ask: "of the
runs where `_reflect()` said `pivot` with confidence > 0.8, how many actually
would have failed anyway if left to run?" — that's the only way to know whether
P4's meta-reflection feature is actually net-positive or just net-different.
Today there's no way to answer that question at all.

## How to Use Effectively

1. Add `confidence: float` to the JSON schema of `REFLECTION_SYSTEM_PROMPT` and
   `VALIDATION_SYSTEM_PROMPT` responses (`llm.py`) — one field, minimal prompt
   change: "include a confidence score 0.0-1.0 for this decision."
2. Start by just *logging* the confidence (via S-05 if it exists, or a plain log
   line otherwise) without changing behavior — you need a baseline of what
   confidence values the model actually produces before picking a threshold to
   act on.
3. Once you have enough logged data to pick a sane threshold, gate `_reflect()`'s
   `pivot`/`stop` on `confidence >= threshold`; below threshold, default to
   `continue` — biasing toward the conservative "keep trying" behavior only when
   the model is actually confident enough to disrupt the run.
4. Don't bother with confidence scores on `diagnose_failure`/`characterize_stock`
   — those are advisory/informational (fed into prompts as context, not acted on
   as a binary control-flow decision), so there's no downstream threshold logic
   that would use the number. Reserve this for calls that actually gate a
   `break`/`continue` decision.

## Implementation Hint — Where This Fits Today

**Entry points, both small and independent:**

- `REFLECTION_SYSTEM_PROMPT` (`llm.py`) + `_reflect()` (`loop.py:939`) — the JSON
  schema `{"decision": "continue|pivot|stop", "new_approach": "...", "reasoning":
  "..."}` gets one more field, and `_reflect()`'s `return result.get("decision",
  "continue")` becomes a two-value read (`decision`, `confidence`) plus a
  threshold check.
- `VALIDATION_SYSTEM_PROMPT` (`llm.py`) + `_validate_idea()` (`loop.py:927`) —
  same shape of change.

**Why this is feasible right now:** both call sites already parse a JSON dict and
already discard everything except one or two fields via `.get(...)` — adding
`confidence` to the schema and reading one more `.get("confidence", 0.5)` is not
a new pattern, it's extending an existing single-field extraction to two fields.

**Where the threshold check plugs in:** `loop.py:352-363`, the block that calls
`_reflect()` and checks `if pivot_decision == "pivot": ...`/`elif pivot_decision
== "stop": ...` — this is where `pivot_decision`/`confidence` would both need to
be returned from `_reflect()` (change its return type from `str` to a small tuple
or dict) and where the `confidence >= threshold` gate gets added before acting on
`pivot`/`stop`.

**Sequencing note:** do this *before* S-10 if both are planned — adding one field
to a text-prompted JSON schema is trivial; if S-10 (native function-calling)
lands first, do the confidence field as part of that migration instead of as a
separate change to avoid touching the same schema twice.

## Potential Bugs to Watch For While Testing

- **`_reflect()`'s return type changes from `str` to something richer** (a tuple
  or small dict carrying both `decision` and `confidence`). Python won't catch a
  missed call site at compile time — `if pivot_decision == "pivot":` silently
  evaluates `False` forever if `pivot_decision` is now a tuple, and the loop just
  quietly stops pivoting/stopping without any error. Grep for every call site of
  `_reflect()` before merging and test each one explicitly, not just the primary
  call in the iteration loop.
- **LLM confidence scores may not be meaningfully calibrated.** Test the actual
  *distribution* of confidence values returned across a batch of real runs before
  picking a threshold — if the model clusters everything around 0.8-0.9
  regardless of actual reliability (a known LLM tendency), a threshold gate does
  nothing and gives false assurance that you're filtering on signal.
- **Don't hardcode a threshold before the logging phase has produced real data.**
  The plan explicitly says "log first, threshold later" — test that this
  sequencing actually happens; it's tempting to skip straight to `if confidence
  >= 0.7` with a guessed number, which defeats the entire point of this
  suggestion (having a *validated*, not assumed, threshold).
- **Threshold gate changes default behavior for existing runs.** Once a threshold
  is added, low-confidence `stop`/`pivot` decisions now fall through to
  `continue` — test that this doesn't silently make runs longer/more expensive
  on average (more iterations executed than before) without that being an
  intentional, measured tradeoff.
