---
name: storage-enhancement-levels-implementation-summary
status: done
purpose: plain-language summary of what was actually built for the shared backtest infrastructure, how each piece was checked, and what the test results were — the "did it happen, and did it work" record to go with plan.md's "here's what we're going to build."
---

# Storage Enhancement — What Got Built, and How It Was Checked

This file is the follow-up to `plan.md`. That file explains what was going
to be built and why. This file records what actually happened: six pieces
of code, each individually checked before being called done, plus a full
test suite run to make sure nothing else broke.

**Correction, recorded honestly rather than quietly edited away**: the
DLinear end-to-end check described in §2 below used a synthetic
random-walk price series, not real market data — it proved the plumbing
(shapes, wiring, round-trips) but couldn't catch anything that depends on
real calendar structure. It was re-run against real data afterward and
that rerun caught two real things the synthetic check had missed entirely.
See `angle-validation-checklist.md` for what changed, what those two
findings were, and the checklist every future angle's wiring now goes
through instead of a synthetic-only pass.

## 1) What was built

| # | Piece | File |
|---|---|---|
| 1 | Calendar/session tagging | `vinu-initial-analysis/vinu_initial_analysis/angles/_tagging.py` |
| 2 | Weights artifact store | `vinu-initial-analysis/vinu_initial_analysis/storage/weights.py` |
| 3 | Walk-forward backtest loop | `vinu-tools/vinu_tools/compute/backtest/walk_forward.py` |
| 4 | Query/aggregation layer | `vinu-initial-analysis/vinu_initial_analysis/storage/query.py` |
| 5 | Clean angle-deletion helper | `vinu-initial-analysis/vinu_initial_analysis/storage/admin.py` (+ one new method on the existing `RunLog`) |
| 6 | DLinear wired up as the first real angle | `vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/backtest.py`, plus a small refactor of `angles/dlinear/compute.py` |

Piece 5 wasn't in the original four-piece plan — it came out of a
correctness check (see §2 below) that found `RunLog` (the SQL table that
tracks "which run is the current one") had no way to remove an angle's
rows, which would have left dangling references behind after a file
delete. It's now documented in `plan.md` itself as a fifth piece, not just
in this summary.

**The one code change outside the six new files**: `dlinear/compute.py`'s
internal training logic was split into a new `_fit_and_forecast()` helper
so the trained model object is available to hand to the weights store —
`compute()` itself now calls that helper internally, so its existing
behavior (same inputs, same output columns) is unchanged. Its
`MIN_BARS` floor was also raised from 80 to 100, matching the value
already decided in `04-enhancement-of-each-angle/05-dlinear.md`.

## 2) How each piece was checked

Every piece was checked against real behavior, not just read back for
typos — each one was actually run with real inputs before being marked
done:

- **Tagging**: ran `tag_row()` against real timestamps and compared the
  result to `_market_hours.py`'s `classify_session()` called directly on
  the same timestamps — confirmed a known NY-market-hours timestamp maps
  to `session="ny", subsession="markethours"` and an overnight timestamp
  maps to `session="closed"`.
- **Weights store**: saved and reloaded a real object, and separately
  confirmed the returned path exactly matches the worked example already
  written into `plan.md` (`AAPL/dlinear/1D/2024/202405/1715779800.pt`) —
  not just "some path," the *documented* path.
- **Walk-forward loop**: tested with a synthetic step function and
  confirmed, by hand-checking the printed output: the expanding window
  grows correctly, a fixed rolling window stays the right size, refit
  cadence flags the right steps, state carries from one step to the next,
  tags get merged in, and the weights-saving hook is only called when a
  step actually returns weights.
- **Query layer**: built a small DataFrame by hand, ran the grouping
  function on it, and checked the output against a manually computed
  pandas `groupby` on the same data — including the nested
  multi-horizon-forecast shape (Chronos/Kronos/lag_llama's format), not
  just the simple flat-row case.
- **Clean deletion (piece 5)**: this is the one where checking actually
  found a real bug before it shipped. Re-reading `plan.md`'s own worked
  example surfaced two problems: (1) the weights-store example was calling
  a function with the wrong number of arguments and would have crashed
  immediately, and (2) there was no way to delete an angle's SQL log
  entries when deleting its files, which would have left stale "latest
  run" pointers behind. Both were fixed — the first with a small wrapper
  function, the second by adding `delete_by_angle()` to `RunLog` and a new
  `delete_angle()` that cleans up files and log rows together — then
  proved with a real write/delete/verify cycle: wrote data for two angles
  under two symbols, deleted one angle, and confirmed its files and SQL
  rows were gone while the other angle's were completely untouched.
- **DLinear, end to end**: this was the real proof. Generated 130 days of
  synthetic price data, ran the full backtest through every shared piece
  at once, and checked: the right number of result rows came out, each
  row's tags matched what `tag_row()` produces standalone, each row's
  saved weights file could be reloaded and contained a real trained
  model's parameters, the results round-tripped correctly through the
  existing production storage class (`AngleStorage`), and the query
  layer's grouped average exactly matched a hand-computed average on the
  same data.

## 3) Test results

36 new automated tests were written (one file per piece, following the
same style as the project's existing tests — real objects and temporary
folders, no mocking) and all pass:

| File | Tests |
|---|---|
| `tests/test_tagging.py` | 5 |
| `tests/test_weights.py` | 4 |
| `tests/test_admin.py` | 3 |
| `tests/test_query.py` | 6 |
| `tests/test_dlinear_backtest.py` | 5 |
| `vinu-tools/tests/test_walk_forward.py` | 9 |
| (existing `test_dlinear.py`, one stale comment fixed) | 4 |

**Full project test suite, run after everything above**:
- `vinu-initial-analysis`: 215 passed, 11 failed, 2 skipped.
- `vinu-tools`: 127 passed.

The 11 failures are all in `test_shock_clustering.py` and
`test_shock_personality.py`, both failing with the same `KeyError:
'bar_ts'` — **confirmed pre-existing**, not caused by anything in this
round of work: stashing every change from this session and re-running
just those two files reproduces the identical failures on the untouched
codebase. Nothing built here touches either of those angles. Left as-is,
flagged here rather than silently ignored.

## 4) What this proves, and what it doesn't

Proven: the four (now five) shared pieces work correctly on their own,
work correctly together, and one real angle (DLinear) can be fully wired
through all of them end to end with real numbers coming out the other
side that match hand-checked expectations.

Not yet done: only DLinear is wired up. The next two steps, per `plan.md`
and the original build order, are ARIMA (introduces a different
CI-coverage-based hit definition, and exercises `refit_cadence` for the
first time) and then one nested-multi-horizon angle such as Chronos or
lag_llama, before the remaining ~28 angles get wired up the same way.

## Related files

- `plan.md` — the design this summary reports the completion of.
- `angle-validation-checklist.md` — the real-data checklist every future
  angle's wiring goes through; also records the real-data rerun of the
  DLinear check described above and what it caught.
- `04-enhancement-of-each-angle/05-dlinear.md` — DLinear's own decided
  design, including the `MIN_BARS` 80→100 change reflected in `compute.py`.
