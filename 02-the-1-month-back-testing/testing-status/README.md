# Testing Status — Convention

Identical convention to `e2e-test-0731/testing-status/README.md` and
`the-stage-2-claude/testing-status/README.md`. Each item under
[../scope-responsibilities/](../scope-responsibilities/) has a folder
here with the same name, containing one running file: **`test-log.md`**.

## `test-log.md` structure

1. **What will be tested / Expected output** — written up front, before
   any implementation happens (already filled in per item, copied from
   the corresponding `scope-responsibilities/` file's "Expected output /
   how to verify" section).
2. **Bug / Fix Log** — starts empty (`_Nothing logged yet_`). As work
   actually happens, numbered entries get appended in the order found:

```markdown
## Bug / Fix Log

### Bug-1 — <one-line summary>
- **Found during:** <what step surfaced this>
- **Date:** <YYYY-MM-DD>
- **Symptom:** <what was observed>
- **Reproduction:** <exact command/request>
- **Severity:** blocker / major / minor

### Fixed-1
- **Root cause:** <confirmed, not guessed>
- **Fix applied:** <files changed, what changed>
- **Verification:** <how it was confirmed fixed>
- **Status:** fixed / wontfix (why) / deferred (why, to when)
```

- Numbers are per item, not global.
- A finding that turns out not to need a fix still gets logged, not
  silently dropped.

## Order matters here more than in prior plans

Item 1 (simulated clock) and item 2 (historical broker) are both
core-`vinu-agent` changes that also run in every real live/paper trading
session. Any bug found in these two items must be re-verified against a
**normal, non-replay session** too, not just the replay path — log that
regression check explicitly in the Bug/Fix entry, don't assume "it works
in replay mode" implies "the live path is unaffected."

## Current state

**As of 2026-08-03 (updated):** all five items have real output from a
full, fixed 20-day run — `run-2026-07-06-2026-07-31-v2` (2026-07-06 →
2026-07-31, AAPL/TSLA/JNJ). Summary, fullest detail in each item's own
`test-log.md`:

- **Item 1/2 (clock guard, historical broker):** held. Lookahead guard
  never leaked in any spot-checked call. **New bug found**: the broker
  never marks a held position to the current price outside of a fill
  event — `historical-fill-broker/test-log.md` Bug-2.
- **Item 3 (day-stepper harness):** 20/20 days completed, ~10 min
  wall-clock, resumable. **New bug found**: the agent stopped calling any
  tool at all for 16 of the 20 days, likely token-budget starvation from
  the reused session's growing history — `day-stepper-replay-harness/
  test-log.md` Bug-5. Also fixed a report-narrative false-positive bug in
  `_parse_action`.
- **Item 4 (P&L + reporting):** `report_month_replay.py` verified against
  the real run; found and fixed both the narrative bug above and the
  broker's frozen-mark issue at the reporting layer (real historical
  closes now used to mark held positions). Corrected result: **-$239.58
  (-0.24%)**, Sharpe -0.23, max_drawdown -3.08%, 1 real trade. See
  `../results/run-2026-07-06-2026-07-31-v2/report.md`.
- **Item 5 (behavioral rubric):** all 20 days read chronologically;
  answers written to
  [`the-project-vision/the-premarket-agents-answers-from-replay.md`](../../the-project-vision/the-premarket-agents-answers-from-replay.md).
  Headline finding: the agent fabricated a JNJ price never present in any
  tool response and repeated it for 13+ days — see that doc's closing
  section.

**Net assessment:** the infrastructure (items 1-4) works correctly and
survived real use. The agent's own behavior (item 5) surfaced two real,
still-unfixed problems — tool-call dropout and a stale price mark — that
mean this run's Section 3 (loss-adaptation) conclusions are honest but
limited. A cleaner behavioral read requires fixing those two before the
next run, not just re-running the same setup again.
