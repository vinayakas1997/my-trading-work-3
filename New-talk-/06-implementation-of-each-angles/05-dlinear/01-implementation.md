---
name: dlinear-implementation
status: phase-1-done
purpose: the real record of implementing DLinear's walk-forward backtest against the shared infrastructure — files touched, how it was built, how it was tested, and the bugs actually found along the way.
---

# 05 — DLinear — Implementation Record

## Correction (found while implementing angle 02, checked back against this one)

DLinear's own decided design (`04-enhancement-of-each-angle/05-dlinear.md`
§3) says `Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | same 6 as
ARIMA` — but `spec.yaml` was left declaring only `1D` this whole time; it
was never actually widened when this angle was built, and real-data
validation (`02-real-scenario.md`) only ever ran against `1D`. This was
missed, not a deliberate scope decision. Fixed: `spec.yaml` now declares
all 6. Per the two-phase timeframe-checking policy decided during angle
01 (`Agents.md`), `1D` stands as this angle's Phase 1 (already validated
for real, see `02-real-scenario.md`); the other 5 are Phase 2 — deferred,
not yet run, tracked here rather than silently left incomplete. `status`
above changed from `done` to `phase-1-done` to reflect this honestly.

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/_tagging.py` | New | Shared calendar/session tagging (built once, used by every angle, not DLinear-specific). |
| `vinu-initial-analysis/vinu_initial_analysis/storage/weights.py` | New | Sharded weights artifact store (shared). |
| `vinu-tools/vinu_tools/compute/backtest/walk_forward.py` (+ `__init__.py`) | New | The generic walk-forward loop (shared). |
| `vinu-initial-analysis/vinu_initial_analysis/storage/query.py` | New | Grouped-aggregation query layer (shared). |
| `vinu-initial-analysis/vinu_initial_analysis/storage/admin.py` | New | `delete_angle()` cross-storage cleanup (shared). |
| `vinu-initial-analysis/vinu_initial_analysis/storage/meta.py` | Edited | Added `RunLog.delete_by_angle()`, needed by `admin.py`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/compute.py` | Edited | Split into `_fit_and_forecast()` (returns the trained model too) + `compute()` (unchanged external behavior, now calls the helper). `MIN_BARS` raised 80→100 per the decided design (`04-enhancement-of-each-angle/05-dlinear.md` §3). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/backtest.py` | New | DLinear's own glue code — `dlinear_step` + `run_dlinear_backtest`. |
| 6 new test files, 1 existing test file's stale comment fixed | New/edited | See "Testing" below. |

## How it was implemented

DLinear was picked as the first angle specifically because its design
touches all four original shared pieces at once (tagging, the loop, the
weights store, query aggregation) — see `05-storage-enhancement-levels/plan.md`
"Deeper rationale" for why.

The only DLinear-specific code is `backtest.py`'s `dlinear_step`, which:
1. Takes `step.history` (bars up to the current point) and calls the
   refactored `_fit_and_forecast()` — the same training logic `compute()`
   already used, now also handing back the trained `nn.Module`.
2. Compares the forecast direction against the actual next bar's direction
   for the `hit` field.
3. Returns `StepResult(row=..., weights=model.state_dict())` so the
   harness saves this step's exact trained model.

`run_dlinear_backtest` wires `tag_row` and a small `_save_weights` closure
(binding `angle_name="dlinear"` — see "Bugs found" below for why this
wrapper has to exist) into `run_walk_forward`, using DLinear's decided
`min_observations=100`.

## Testing

36 new automated tests across the 6 new shared-infrastructure files plus
DLinear's own backtest module, all in the existing project style (real
objects, `tempfile.TemporaryDirectory()`, no mocking):

- `tests/test_tagging.py` (5), `tests/test_weights.py` (4),
  `tests/test_admin.py` (3), `tests/test_query.py` (6),
  `tests/test_dlinear_backtest.py` (5) — in `vinu-initial-analysis`.
- `vinu-tools/tests/test_walk_forward.py` (9).
- `tests/test_dlinear.py` — one stale comment fixed (referenced the old
  `MIN_BARS=80`), all 4 existing tests still pass unchanged, confirming
  the `compute.py` refactor didn't change `compute()`'s external behavior.

Full suite after everything: `vinu-initial-analysis` 215 passed / 11
failed (pre-existing, unrelated — see below) / 2 skipped;
`vinu-tools` 127 passed.

**Real-data validation** (see `02-real-scenario.md` for the actual
numbers): first proven against synthetic random-walk data (structural
check only), then re-run against 186 real AAPL daily bars fetched via
`yfinance` — see `05-storage-enhancement-levels/angle-validation-checklist.md`
for the full checklist and what the real-data pass caught that the
synthetic pass didn't.

## Bugs found

1. **`weights_sink` argument-count mismatch** (found reviewing
   `05-storage-enhancement-levels/plan.md`'s own worked example, before
   any code existed): `WeightsStore.save()` needs 5 arguments including
   `angle_name`, but the generic harness's `weights_sink` contract only
   ever supplies 4 (it has no concept of which angle is calling it).
   Fixed by having `backtest.py` wrap the call in a `_save_weights`
   closure that binds `"dlinear"` — the pattern every future angle's own
   glue code must repeat with its own name.
2. **`RunLog` had no way to delete an angle's rows** (found the same
   review pass): deleting an angle's files without also removing its
   `RunLog` rows would leave `get_latest_run()` resolving to a `run_id`
   whose file no longer exists. Fixed by adding `RunLog.delete_by_angle()`
   and a new `storage/admin.py` piece — not in the original four-piece
   plan, added as a fifth piece as a direct result of this check.
3. **Datetime-unit bug while fetching real validation data** (found
   during the real-data validation pass, not in the shared infrastructure
   itself): an initial `bar_ts` computation from `yfinance`'s output
   divided by `10**9` assuming nanosecond-precision timestamps; this
   environment's pandas returns second-precision `datetime64[s]`, so every
   computed `bar_ts` silently collapsed to `1`. Caught immediately because
   the row-count and gap-spacing checks in the validation checklist
   flagged obviously-wrong output — exactly the kind of mistake a
   synthetic-only check (which never touches real datetime parsing) can't
   catch.
4. **Session tagging is trivially `"closed"` for all 1D bars** — not a
   code bug (this is correct behavior — a midnight-UTC timestamp never
   falls inside a real trading session), but a real finding about what
   query examples are meaningful for a 1D-only angle like DLinear. See
   `angle-validation-checklist.md` finding #1.

The 11 pre-existing full-suite failures (`test_shock_clustering.py`,
`test_shock_personality.py`, both `KeyError: 'bar_ts'`) were confirmed,
by stashing every change from this work and re-running just those two
files, to already exist on the untouched codebase — unrelated to anything
built here, not fixed as part of this work.

## Related files

- `02-real-scenario.md` — the real example proving this actually works.
- `../plan.md` — the overall implementation plan and status table.
- `../../05-storage-enhancement-levels/plan.md` and
  `implementation-summary.md` — the shared infrastructure this angle was
  built and proven against.
- `../../04-enhancement-of-each-angle/05-dlinear.md` — the decided design
  this implementation follows.
