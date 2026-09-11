# Scenario 03 — Sideways chop

## Plan

Written before anything is run. Re-verified against the real code first
(not assumed): `_maybe_enter()` is only ever called when
`_find_open_position(symbol) is None` — once a position exists, entry
logic is structurally unreachable for that symbol until the position
closes. So "no phantom entries on noise" is already guaranteed by
`cycle()`'s own control flow, not something chop could break — there is
nothing meaningful to test there. The real, non-trivial claim worth
checking is the one this actually can threaten: **once a position is
open, does noisy chop cause a spurious full exit or repeated
whipsaw-style action, or does the system correctly just hold through it?**

An open AAPL position, entered at $100, with a normal invalidation
threshold (`unrealized_pnl_pct <= -0.08`) and no contingency rules. Fed
12 consecutive bars chopping within a tight ±2% band around entry (102,
98, 101, 99, 102, 98, 101, 99, 102, 98, 101, 99) — never once approaching
the -8% invalidation threshold. `_evaluate_open_position` is driven bar by
bar, same convention as scenario 01/02.

One thing intentionally left open rather than forced: the trailing-stop
ratchet (`trailing_stop_for`) populates `position.stop_loss` automatically
once enough price history exists, regardless of whether a backstop was
ever placed at entry (confirmed while writing the original trailing-stop
scenario) — and once a stop exists, the bracket-partial check becomes
eligible too. Whether ±2% chop is enough to cross a full 1R against that
self-generated stop isn't obvious from reading the code alone (it depends
on the ATR computed from this exact chop pattern) — so the Expected
Result below accepts `bracket_partial` as a legitimate non-exit outcome,
same as the original trailing-stop scenario already does, rather than
predicting a number that would just be a guess.

## Expected Result

1. Across all 12 bars, `action` is never `invalidation_exit`,
   `exit_not_filled`, `exit_blocked_by_breaker`, or any `rebalance_*` —
   only `hold` or `bracket_partial` are acceptable outcomes.
2. The position is never fully closed — `list_open_positions` for AAPL
   returns a nonzero qty after every bar.
3. No exception is raised at any bar (the chop pattern, including its
   down-legs, doesn't trip anything unexpected).

## Execution Result

Built as `vinu-live/tests/test_pre_live_scenarios.py::TestScenarioSidewaysChop::test_tight_chop_never_produces_a_spurious_full_exit`:

```
tests/test_pre_live_scenarios.py::TestScenarioSidewaysChop::test_tight_chop_never_produces_a_spurious_full_exit PASSED
```

Full `vinu-live` suite after: 309 passed (2 pre-existing, unrelated `test_auth.py` failures — same baseline throughout this audit).

Traced the real bar-by-bar actions separately (not just the pass/fail) to answer the open question the Plan flagged: does the self-generated trailing stop's 1R ever get crossed by this chop? It did **not** — every single bar returned `hold`:

```
bar  price  action  stop_loss  qty
1    100.0  hold    None       10.0
2    102.0  hold    None       10.0
3    98.0   hold    92.0       10.0
4    101.0  hold    95.0       10.0
5    99.0   hold    95.0       10.0
6    102.0  hold    96.4       10.0
7    98.0   hold    96.4       10.0
...  (stop stays at 96.4 for the rest, qty stays 10.0 throughout)
```

## Reasoning

The trailing stop populated and ratcheted correctly (92.0 → 95.0 → 96.4, then held, never loosening — consistent with the original trailing-stop scenario) but the resulting risk distance (100 → 96.4, ~3.6%) was always larger than the ±2% chop ever moved in the position's favor, so the bracket-partial's 1R trigger was never reached. Both mechanisms behaved exactly as designed on their own, and the combination of the two produced the clean "hold the whole way through" result the scenario predicted as the most likely outcome — no surprises, no whipsaw, no spurious action on noise.

This is the same shape of result as scenarios 01 and 02: nothing was broken, and this scenario's value is in having actually checked it rather than assumed it. Worth noting for the record: this result is chop-amplitude-dependent, not a universal guarantee — a wider chop band relative to a given symbol's own ATR *could* still cross 1R and trigger a `bracket_partial` (which, per scenario C1c's own fix, is proportionally small near 1R and capped at 75%, not a full exit) — but a *full* `invalidation_exit` on pure noise would still require the chop to reach the plan's real threshold (-8% here), which by definition isn't "chop" anymore.

## Action Taken

**No fix needed** — the real behavior matched the known-correct answer (in fact the cleanest possible outcome, `hold` at every single bar) on the first run.

No new gaps flagged from this one — unlike scenarios 01 and 02, this scenario's boundary (chop-amplitude-dependence) is already explicitly acknowledged above rather than left as an open question.
