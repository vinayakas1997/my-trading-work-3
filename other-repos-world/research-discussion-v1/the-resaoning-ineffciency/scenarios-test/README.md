# scenarios-test

Expanded pre-live mechanical scenarios (no LLM) -- the follow-on to
`vinu-live/tests/test_pre_live_scenarios.py`'s original 3. One scenario
closed out fully (plan -> build -> run -> fix if needed -> retest) before
moving to the next -- see each subfolder's `scenario.md` for the full
record.

## Status

| # | Scenario | What it checks | Status |
|---|---|---|---|
| 01 | [Gap-down crash](01-gap-down-crash/scenario.md) | Does the invalidation exit react correctly to a single-bar -25% crash, not just a gradual move? | **done** -- confirmed correct, no fix needed |
| 02 | [Kill switch engaged mid-cycle](02-kill-switch-mid-cycle/scenario.md) | Blocks a would-be entry, still lets a reduce-only exit through -- in the same cycle | **done** -- confirmed correct, no fix needed |
| 03 | [Sideways chop](03-sideways-chop/scenario.md) | Proves the system holds through tight noise -- no spurious full exit or whipsaw | **done** -- confirmed correct, no fix needed |
| 04 | [Broker outage mid-cycle](04-broker-outage-mid-cycle/scenario.md) | Entries pause, but does an exit still fire correctly? | **done** -- confirmed correct, no fix needed |
| 05 | Multiple correlated positions moving together | Does the correlation/concentration overlay actually kick in? | pending |
| 06 | Broker-side stop already closed the position overnight | Does `_reconcile_book_with_broker` recover correctly when the real resting stop fired before the next cycle even runs? (Flagged while building scenario 01, not started.) | pending |
| 07 | `vinu-agent`-side kill-switch enforcement | Does the REAL `OrderGuard`/`kill_switch.py` allow a `reduce_only` order through a halt (the authoritative check scenario 02 couldn't reach from the orchestrator side)? (Flagged while building scenario 02, not started.) | pending |

## Format

Each subfolder's `scenario.md` has five sections, written in this order:

1. **Plan** -- the exact synthetic setup (prices, plan config, broker
   state), written before anything is run.
2. **Expected Result** -- the known-correct answer, also written before
   running anything (so a bad result can't get quietly rationalized after
   the fact).
3. **Execution Result** -- what the real orchestrator code actually did,
   pasted from a real test run.
4. **Reasoning** -- why the result matched or didn't, and what it reveals
   about the real code.
5. **Action Taken** -- fixed / no fix needed / flagged for later, with the
   commit if something was fixed. A scenario is closed only once this
   section is filled in.
