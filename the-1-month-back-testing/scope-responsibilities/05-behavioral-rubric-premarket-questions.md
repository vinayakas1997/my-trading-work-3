---
name: behavioral-rubric-premarket-questions
component: analysis only (reads item 3/4 output + the premarket-questions doc)
status: not-started
---

# Item 5 — Behavioral Rubric Against the Premarket-Readiness Questions

## What this is

The actual payoff for the user's earlier question — "does the agent
understand what its plan should be, does it adapt to losses, does it
maintain risk discipline" — answered by reading real transcripts from a
real (simulated) month, instead of arguing about it in the abstract.

This item is analysis, not code. It reads item 3's day-by-day transcripts
and item 4's report, and scores them against specific, already-written
questions in
[`../../the-project-vision/the-premarket-agents-questions.md`](../../the-project-vision/the-premarket-agents-questions.md).

## Be precise about what this replay can and cannot answer

**Can answer** (regular-session behavior, using data that genuinely
existed at each simulated point in time):
- Section 1 (Signal & Strategy Validity) — does the agent's stated
  reasoning lean on `significance_score`/sentiment for *direction* (a
  proven-negative mechanism — flag every instance)? Does it treat a
  low-sample ticker (JNJ, AUC 0.75 on 6 test positives) with the same
  confidence as a high-sample one (AAPL/TSLA)?
- Section 3 (Risk Management & Loss Adaptation) — after a losing day or
  string of losing days in the replay, does the agent's subsequent
  reasoning change (smaller size, more caution, explicit acknowledgment
  of drawdown)? Does it ever reference the graduated risk-budget tiers
  (`risk_budget.py`'s -1%/-2%/-3%) on its own, unprompted — or does
  nothing change until the hard -20% circuit breaker would fire?
- Section 6 (Human-in-the-Loop & Governance), partially — does the agent's
  behavior around `require_confirmation` make sense in a compressed
  day-by-day setting (this won't test real Telegram/Discord timing, but
  will show whether the agent's own request-for-confirmation language is
  coherent and appropriately cautious).

**Cannot answer** (structurally out of scope for this replay):
- Section 2 (Premarket-Specific Conditions) — this replay uses
  regular-session daily/intraday bars; there is no premarket data
  anywhere in the stack to replay (confirmed, a genuine zero). Do not
  write a rubric answer implying premarket readiness was tested here.
- Section 7 (Promotion Path) — `ShadowEvaluator` is dormant regardless of
  this replay; this replay is not the same thing as ShadowEvaluator and
  doesn't substitute for wiring it up.
- Real execution quality (Section 4) — item 2's historical broker uses a
  cost model, not real market microstructure; it can show whether the
  *strategy* was profitable on paper, not what real slippage would do to
  it.

## How to actually do this (process, not code)

1. Read every day's transcript from item 3 in chronological order — don't
   sample or skip days; the whole point is catching a change in behavior
   over the sequence, which requires seeing the sequence.
2. For each of the "can answer" questions above, extract concrete
   evidence: quote the specific transcript line/day that supports or
   contradicts it. "The agent seemed cautious" is not evidence; "on day
   14, after a -2.3% day-over-day account drop on day 13, the agent's
   message explicitly reduced AAPL position size from X to Y and stated
   the reason" is.
3. Write the answers directly into a copy of the relevant sections of
   `the-premarket-agents-questions.md` — or a new sibling file,
   `the-project-vision/the-premarket-agents-answers-from-replay.md` — so
   the evidence-backed answers live next to the questions they answer,
   clearly marked as "answered via 1-month replay, not live trading."
4. Flag any question the replay's evidence contradicts sharply (e.g., the
   agent never once referenced risk tiers, or its reasoning subtly
   depended on knowing the "future" in a way that suggests the lookahead
   guard has a gap) as a new bug against item 1 or item 2, not as a
   philosophical finding — if the guard leaked, that's a code bug to fix
   and rerun against, not a permanent conclusion about the agent.

## Files to touch

- Read-only: item 3's transcript output, item 4's report,
  `the-project-vision/the-premarket-agents-questions.md`.
- New: `the-project-vision/the-premarket-agents-answers-from-replay.md`
  (or inline edits to the questions file, marked clearly per-question as
  answered-via-replay vs. still open) — pick whichever keeps the
  questions document itself clean; don't silently overwrite the questions
  file's original text.

## Expected output / how to verify

- Every "can answer" question above has a concrete, evidence-cited
  answer (quoting specific days/transcripts), not a vibe-based summary.
- Every "cannot answer" question is explicitly marked as out of scope
  for this exercise, not silently skipped (a missing answer and a
  correctly-scoped non-answer must be distinguishable to a future
  reader).
- Any lookahead or guard-failure discovered during this reading gets
  logged as a `Bug-N` against item 1 or item 2's test-log, with the
  specific transcript line as the reproduction — not just noted in
  prose here and forgotten.
