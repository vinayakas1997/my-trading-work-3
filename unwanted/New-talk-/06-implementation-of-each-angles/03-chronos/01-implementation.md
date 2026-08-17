---
name: chronos-implementation
status: phase-1-done
purpose: the real record of implementing Chronos's walk-forward backtest against the shared infrastructure — files touched, how it was built, how it was tested, and every bug found along the way.
---

# 03 — Chronos — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-infra/models.py` | Edited | Added `chronos-t5-large` to the `MODELS` registry (only `chronos-t5-tiny` was registered) — needed before `ensure_model("chronos-t5-large")` could resolve at all. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/chronos/compute.py` | Edited | `CHECKPOINT` raised `tiny`→`large` (710M params) per the decided design; `MIN_OBSERVATIONS` raised 30→512 (a **fixed** context requirement, not a growing floor); extracted `_forecast()` helper `compute()` and `backtest.py` both call. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/chronos/backtest.py` | New | `chronos_step` (nested `predictions` dict, per-horizon-step hit) + `run_chronos_backtest`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/chronos/naive_baseline.py` | New | Naive baseline extended to the 5-step horizon. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/chronos/spec.yaml` | Edited | Stale `outputs.description` still said "via amazon/chronos-t5-tiny" — fixed to `large`. (`time_formats` was already widened to 6 in an earlier batch pass.) |
| `vinu-initial-analysis/vinu_initial_analysis/storage/query.py` | Edited | `unnest_predictions` now casts a numeric-string `horizon` key back to `int` — see Bug 2. |
| `vinu-initial-analysis/tests/test_chronos_backtest.py` | New | 6 tests, see "Testing". |

## How it was implemented

Third angle wired against the shared infrastructure, and the **first with
a genuine multi-step forecast and a nested storage shape** — the first
real exercise of `query.py`'s `unnest_predictions()`, per
`06-implementation-of-each-angles/plan.md`'s build order.

`chronos_step` calls the real pretrained pipeline (cached in-process
after first load) on a fixed 512-candle context, and for each of the 5
horizon steps checks `p10 <= actual <= p90` independently — the decided
hit definition. No weights store: nothing is trained here, the same
pretrained weights are reused across every call. No refit-cadence
concept either: unlike ARIMA, Chronos has no "fit" phase to skip — every
single step is a real, independent inference call.

## Real cost — measured, not estimated (closes the design doc's own open caveat)

The design doc's §7 explicitly flags real compute cost as unmeasured.
Benchmarked directly on this CPU-only environment (confirmed: no GPU —
`torch.cuda.is_available() == False`):
- Pipeline load: ~7s (one-time, cached).
- **Single forecast call: ~13-15s** (`chronos-t5-large`, 512-candle
  context, `num_samples=64`, CPU).
- No refit-cadence trick applies (see above) — every step costs the full
  ~14s. A full walk-forward backtest at real scale (e.g. `1H`'s ~495
  possible steps) would take on the order of **~2 hours** — genuinely
  too long for a single validation pass. Phase 1 was deliberately run on
  a **small real slice** (9 steps) instead of a full backtest — see
  "Real-data validation" below.

## Testing

6 new tests in `tests/test_chronos_backtest.py`. Unlike ARIMA/DLinear's
per-step synthetic loops, this suite runs the real model only **twice**
total (one module-scoped 2-step backtest fixture, reused across 5
assertion tests, plus one more for the naive baseline) — real 710M-model
calls are too expensive to loop dozens of times in a unit test. Covers:
row count, tag correctness, nested-predictions structure (5 keys, each
with p10/median/p90/actual/hit), hit matching real band membership,
absence of `weights_ref`, and the naive baseline's parallel structure.
All 6 pass (~33.5s — real model calls, not mocked).

**Real-data validation**: `1D` (this angle's usual coarsest timeframe)
turned out to be **infeasible for Phase 1** — only 125 real daily AAPL
bars are available (6 months), far short of the 512-candle requirement;
512 daily candles need roughly 2 years of history. `1H` (1,011 real
bars) is the coarsest timeframe with enough real data. Given the ~14s/
step cost above, ran a **deliberately small real slice** — the most
recent 525 real 1H bars (525 = 512 + horizon 5 + 8 extra steps) — for 9
real steps, not the full ~495-step backtest that dataset could support.
This is a genuine deviation from every other angle's "run the full
Phase-1 timeframe" pattern, made explicitly and recorded here, not
silently downsized.

Full real-output example, tags, storage round-trip, and the
`unnest_predictions` check are in `02-real-scenario.md`.

## Bugs found and fixed

**Bug 1 — `chronos-t5-large` wasn't in the model registry.**
`vinu-infra/models.py`'s `MODELS` dict only registered `chronos-t5-tiny`;
`ensure_model("chronos-t5-large")` raised `ValueError: Unknown model`.
Found on the very first real download attempt, before any backtest code
existed.
**Fix 1**: added `"chronos-t5-large": "amazon/chronos-t5-large"` to the
registry, same pattern as every other entry.

**Bug 2 — nested `predictions` dict with integer keys can't be written to
parquet.** `pyarrow.lib.ArrowTypeError: Expected dict key of type str or
bytes, got 'int'` — the design doc's own illustrative example (§4) shows
`predictions: {1: {...}, 2: {...}, ...}` with integer keys, but that
shape isn't actually parquet-serializable. Found on the first real
storage-write attempt with real Chronos output — not caught by unit
tests (which never wrote through real `AngleStorage`).
**Fix 2**: `chronos_step`/`naive_step` now key `predictions` by string
(`"1"`-`"5"`), and `query.py`'s shared `unnest_predictions()` casts a
numeric-string key back to `int` for the resulting `horizon` column, so
this is invisible to every caller past the storage layer — one shared
fix, not a per-angle workaround, since any future nested-predictions
angle (Kronos, lag_llama, iTransformer, per the design docs' own list)
would hit the identical bug otherwise.

**Real finding, not a bug — degenerate (zero-width) p10=median=p90
bands.** On a real, low-relative-volatility 512-candle context (std=0.69
on a ~313 price level, ~0.22%), both `chronos-t5-tiny` and
`chronos-t5-large` produced *bit-identical* p10/median/p90 across
several horizon steps — confirmed genuine and reproducible (not specific
to the `large` checkpoint, not a code bug) by reproducing it on both
checkpoints on the identical context, then confirming a more volatile
real window (std=13.8, ~20x higher) produces real nonzero spread,
especially at later horizon steps. Mechanism: Chronos's
`MeanScaleUniformBins` tokenizer (4096 bins over a fixed normalized
range) can concentrate the vast majority of its 64 sampled paths onto a
single discretized bin when the context's real variation is small
relative to that scale. The existing `p10 <= actual <= p90` hit check
already handles this correctly on its own (a zero-width band simply
requires exact equality to count as a hit, which real continuous price
data essentially never satisfies) — no special-casing was needed, this
is recorded as a real model characteristic worth knowing, not fixed.

**Real finding, not a bug — naive baseline beat Chronos on RMSE at every
horizon step**, and hit-rate *increased* with horizon (55.6%→100%)
rather than decaying as the design doc's own illustrative example
anticipated. Both recorded honestly — with the important caveat that
this is only 9 real steps (the deliberately small Phase-1 slice), far
too small a sample to draw a real conclusion from either way. A larger
Phase 2 run would be needed before either finding means anything.

**Bug 3 — the parameter upgrades broke the pre-existing `test_chronos.py`
tests, and one of my own new tests had a stale assertion.** Two separate
issues, caught only by running the *full* suite, not the new test file in
isolation:
- `test_real_pretrained_pipeline_forecasts_expected_length` and
  `test_pretrained_backend_actually_loads_in_this_environment` both built
  synthetic bars with `n=200` — fine under the old `MIN_OBSERVATIONS=30`,
  now insufficient for the decided `512`, so `compute()` correctly
  returned `insufficient_data` and the tests' `status == "ok"` assertions
  failed. The second test also still asserted `checkpoint ==
  "amazon/chronos-t5-tiny"`, stale after the `large` upgrade.
- My own new `test_predictions_nested_dict_has_all_five_horizon_steps`/
  `test_naive_baseline_predictions_shape` asserted `predictions.keys() ==
  {1, 2, 3, 4, 5}` (ints) — written before Bug 2's string-key fix, never
  re-checked against it.
**Fix 3**: raised both `test_chronos.py` tests' synthetic bar counts to
`n=512`, updated the checkpoint assertion to `large`, and updated both new
tests' key assertions to `{"1", "2", "3", "4", "5"}`. All 10 chronos tests
pass together (55.3s — real model calls). This is exactly why the full
suite gets run after every angle, not just that angle's own new test
file — this class of breakage is invisible otherwise.

**Full `vinu-initial-analysis` suite**: 239 passed (up from 233
pre-this-angle — the 6 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `00-plan.md` — the pre-implementation plan this followed (written before the real benchmark numbers were known).
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/03-chronos.md` — the decided design.
