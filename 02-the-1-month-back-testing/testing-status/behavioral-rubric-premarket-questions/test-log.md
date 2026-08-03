# behavioral-rubric-premarket-questions — Test Log

## What will be tested / Expected output

- Every "can answer" question from the scope doc (Sections 1, 3, and part
  of 6 of `the-premarket-agents-questions.md`) has a concrete,
  evidence-cited answer quoting specific days/transcripts — not a
  vibe-based summary.
- Every "cannot answer" question (Sections 2, 7, real execution quality)
  is explicitly marked out of scope for this exercise, not silently
  skipped.
- Any lookahead or guard-failure discovered while reading transcripts is
  logged as a `Bug-N` against item 1 or item 2's own test-log, with the
  specific transcript line as reproduction.
- Full detail: [../../scope-responsibilities/05-behavioral-rubric-premarket-questions.md](../../scope-responsibilities/05-behavioral-rubric-premarket-questions.md)

## Bug / Fix Log

### Verification results (2026-08-03) — full read of `run-2026-07-06-2026-07-31-v2`
- All 20 days read chronologically, not sampled (`thinking.json` +
  `response.json` + `account_snapshot.json` per day, cross-checked against
  raw tool call/result content, not just the final narrative text).
- Answers written to
  [`the-project-vision/the-premarket-agents-answers-from-replay.md`](../../../the-project-vision/the-premarket-agents-answers-from-replay.md)
  (kept as a sibling file, questions doc left untouched, per the item's own
  instruction).
- Sections 1, 3, and the applicable part of 6 answered with concrete,
  quoted evidence. Sections 2, 4, and 7 explicitly marked out of scope,
  not silently skipped.
- **Two lookahead/guard-failure candidates checked, neither confirmed as a
  guard leak:** (a) the frozen position mark could in principle look like
  a lookahead issue (numbers not updating) but is the opposite — it's the
  agent seeing *stale past* data, never future data, so it's a broker
  mark-to-market bug (logged as Bug-2 in `historical-fill-broker/test-log
  .md`), not an item 1/2 lookahead violation; (b) spot-checked several
  days' `get_stock_price`/`get_features` calls for any date past that
  day's `_as_of` clamp — none found, the lookahead guard held throughout
  the parts of the run that made real tool calls.
- **New finding not previously logged anywhere:** the agent fabricated a
  JNJ price (`$162.45`, first appearing 2026-07-09) that does not
  correspond to any real tool response this session, and repeated it
  verbatim across 13+ subsequent days as if it were current data. Logged
  in the answers doc's closing section; not filed as an item 1/2 bug since
  it isn't a lookahead/guard issue — it's a model-hallucination-under-
  token-pressure question, flagged for separate investigation.
- **Status:** item 5 complete for this run. Re-running item 5 against a
  future replay would be worthwhile once `day-stepper-replay-harness`'s
  Bug-5 (tool-call dropout) and `historical-fill-broker`'s Bug-2 (frozen
  mark) are actually fixed — this run's answers to Section 3 in particular
  are honest about being limited by those two bugs, not a clean read of
  the agent's real risk-adaptation behavior.
