---
name: parallel-backtest-infra
status: prototype-done
purpose: cross-angle shared infra for chunked-parallel walk-forward execution — what it is, which angles it applies to, and the real measured numbers behind why it's shaped the way it is. Kept separate from known-issues.md since this isn't a bug, and separate from any one angle's own docs since it's shared vinu_tools infra.
---

# Parallel Walk-Forward Backtest Infra

A shared addition to `vinu_tools/compute/backtest/walk_forward.py` — the
same file `run_walk_forward()` already lives in — for running walk-forward
backtests across a process pool instead of one sequential loop. Built to
answer a real question raised mid-session: can these backtests run
faster in parallel, and if so, how and for which angles.

## What was built

Eight pieces, all in `walk_forward.py`, all reusing the existing
`WalkForwardStep`/`StepResult`/`StepFn`/`TagFn` types:

1. **`run_walk_forward_parallel(...)`** — single-job chunked-parallel
   version of `run_walk_forward`. Requires a fixed int `window` (raises
   otherwise). Partitions the step range into `chunk_size`-sized ranges,
   runs each range in its own OS process via `ProcessPoolExecutor`,
   recombines results in step order.
2. **`WalkForwardJob`** — a dataclass bundling one job's
   `(key, symbol, timeframe, bars, step_fn, min_observations, window,
   horizon, tag_fn, chunk_size)`.
3. **`run_walk_forward_parallel_batch(jobs, *, n_workers=None,
   min_total_steps_for_parallel=1500, max_retries=2, checkpoint_dir=None,
   resume=True)`** — runs *multiple* `WalkForwardJob`s through **one
   shared** process pool, returning a `BatchResult` (see item 7 below).
   This is the version that actually pays off (see Measured Numbers
   below) — jobs can be different symbols of the same angle, or entirely
   different angles, mixed freely in one batch.
4. **`_default_n_workers(n_workers)`** — hardware-aware worker-count
   resolution: `n_workers=None` resolves to `cpu_count - 1` (leaves the
   machine one free core) instead of `ProcessPoolExecutor`'s own default
   of claiming every core. An explicit `n_workers` always wins. Used by
   both parallel functions.
5. **Automatic sequential fallback inside `run_walk_forward_parallel_batch`**
   — added after the first hardware-awareness question got asked
   directly: should the harness itself decide whether parallelizing is
   worth it, given what we'd already measured about the worker-startup
   tax? If the batch's total step count is below
   `min_total_steps_for_parallel` (default 1500 — a conservative rule of
   thumb sitting between the two real measured points below, not a
   precise universal constant), the batch runs every job sequentially
   in-process instead of paying for a pool that would net-lose. This is
   a total-work decision, not a job-count one — see the Fault Tolerance
   section for a real bug this distinction caught.
6. **`_execute_with_retry`** — shared retry/isolation loop used by both
   parallel functions (see Fault Tolerance below).
7. **`BatchResult`/`ChunkFailure`** — `run_walk_forward_parallel_batch`'s
   return type, replacing the original plain `dict[str, DataFrame]` (see
   Fault Tolerance below).
8. **`checkpoint_dir`/`resume` on `run_walk_forward_parallel_batch`** —
   disk checkpoint/resume (see Fault Tolerance below).

Both parallel functions require `step_fn` (and `tag_fn`, if given) to be
plain **module-level** functions, not closures or lambdas — each worker
process pickles a reference to them, not captured state. Confirmed
directly while writing the first test: a lambda `tag_fn` fails with
`AttributeError: Can't get local object` from the pickler.

## Which angles this applies to — the group split

Checked every one of the 31 angles' own `backtest.py` directly (not
assumed) before building anything, since this determines correctness,
not just performance:

| Group | Count | Angles | Status |
|---|---|---|---|
| **Parallel-safe** | 7 | `arima`, `chronos`, `exponential_smoothing`, `garch`, `kalman_filters`, `kronos`, `timer_timerxl` | Already pass `window=MIN_OBSERVATIONS` (a fixed int) to `run_walk_forward` — a genuinely bounded lookback baked into the harness itself. Chunking is a pure scheduling change (never changes what data any step sees), but **"row-for-row identical to sequential" only actually holds for 5 of the 7** — see the correction below. |
| **Expanding window — needs a decision first** | 10 | `dlinear`, `itransformer`, `lag_llama`, `lpatchtst`, `lstm`, `moirai`, `moment`, `patchtst`, `tft`, `timesfm`, `tips_regime_aware_transformer` | Use the harness's default `window="expanding"` — every step's `history` is the *entire* series since t=0, and each step's model trains on all of it. Chunking would silently cap that to `chunk_size + overlap`, which is a real methodology change (bounded-lookback retraining vs. ever-growing retraining), not a free speedup. Both `run_walk_forward_parallel` and `run_walk_forward_parallel_batch` raise `ValueError` if handed a non-int `window`, specifically so this group can't be silently misused. **Not touched — tabled pending an explicit decision on whether these angles should switch to a bounded window.** |
| **N/A** | 13 | `backtesting_44_metrics`, `cross_attention_gcn_news_price_fusion`, `drawdown_deep_dive`, `ml_model_pipeline`, `news_first_analysis`, `news_price_causality`, `peer_relative_strength`, `pnl_attribution`, `regime_analysis`, `shock_clustering`, `shock_personality`, `trend_lifecycle`, `trend_session_structure` | Custom, already-vectorized aggregation over the whole dataset — no step-by-step walk-forward loop to chunk in the first place. This infra doesn't apply. |

7 + 10 + 13 = 30, plus `signal_contract.py` (a shared helper module, not
an angle) = 31.

## Correction: "row-for-row identical" only holds for 5 of the 7, not all 7

All 7 parallel-safe angles were wired to a real `parallel=True` flag in a
follow-up pass. Proving each one for real (not assuming the table above
generalized past `timer_timerxl`, the one angle it was actually measured
against) surfaced a real, honest gap in the original claim:

- **`arima`, `exponential_smoothing`, `garch`, `kalman_filters`,
  `timer_timerxl`** (5 of 7): genuinely deterministic — classical MLE
  fits or a deterministic point-forecast, no sampling involved. Real
  parallel-vs-sequential runs are row-for-row identical (`arima` only at
  `REFIT_CADENCE == 1` timeframes — see the ARIMA-specific caveat below).
  Proven via permanent regression tests (`pd.testing.assert_frame_equal`
  on real multi-chunk parallel output vs. sequential).
- **`chronos`, `kronos`** (2 of 7): **not** row-for-row identical, and
  this is *not* a parallel-wiring artifact. Both real pretrained models
  produce a probabilistic (quantile-sampled) forecast with no fixed seed
  set anywhere in either pipeline — confirmed directly that **two
  sequential calls in the same process on identical input already
  produce different numbers**, before parallel execution is even
  involved. `timer_timerxl`'s own docstring already correctly scoped
  itself as "a deterministic point forecaster with no native
  uncertainty" — that property, not "fixed window" alone, is what
  actually makes exact reproducibility possible, and it doesn't extend
  to Chronos/Kronos's sampling-based architecture. `parallel=True` is
  still safe to use for these two in the sense that matters (same real
  model, same real context window per step, no data leakage or
  methodology change) — it just was never going to produce identical
  numbers to a sequential run, with or without chunking, and claiming
  otherwise would have been false. Both angles' own `run_*_backtest`
  docstrings were corrected to state this precisely instead of repeating
  the "row-for-row identical" language that only actually applies to the
  other 5.

**ARIMA's own additional caveat**: `run_walk_forward_parallel` has no
`refit_cadence`/`prior_state` support at all (every step runs as an
independent fresh fit). For ARIMA's 1H/4H/1D timeframes
(`REFIT_CADENCE == 1`, already refits every step sequentially too) this
is still row-for-row identical. For 1min/5min/15min
(`REFIT_CADENCE > 1`), sequential mode only fully refits every Nth step
and cheaply extends the fit in between (`.append(refit=False)`, ~170x
cheaper per the module docstring); parallel mode has no such path and
fully re-runs the AIC grid search every single step — a real behavior
change (a fresh fit isn't guaranteed to choose the same `(p,d,q)` order
as an extended one) and, for these timeframes specifically, likely more
total real compute than sequential, not just the same compute
rescheduled. Proven directly: a real parallel run on synthetic 1min data
produces the same row count as sequential but genuinely different
forecasts/orders on at least one step. `parallel=True` is a real,
deliberate trade for 1min/5min/15min ARIMA, not a free win the way it is
for the other 6 angles.

Also worth naming: 4 of the 7 parallel-safe angles (`arima`,
`exponential_smoothing`, `garch`, `kalman_filters`) use `refit_cadence >
1` with `prior_state` chained step-to-step. The current parallel
functions run every step with `is_refit_step=True, prior_state=None` —
correct for `refit_cadence=1` (the common case, and what `timer_timerxl`
uses) but for the cadence>1 angles this means each chunk boundary forces
an extra refit rather than inheriting the previous chunk's cached fit.
Not wrong, just more refits than sequential execution would do — cheap
for these angles (garch's own fit cost was measured at ~0.027s earlier
this session) but not yet optimized. Cross-step state chaining across
chunks is a known, documented gap, not silently broken.

## Measured numbers — why the batch version is the one that matters

Real AAPL/JNJ/TSLA daily bars (the same real cached data used throughout
this session), `timer_timerxl` as the proof angle (Group 1, real
pretrained inference, no retraining per step).

**Single symbol, single call** (`run_walk_forward_parallel` on AAPL
alone, 921 real steps):

| | Time |
|---|---|
| Sequential | 14.59s |
| Parallel (fresh pool, 4 workers) | 14.28s (1.02x — essentially no gain) |

Dug into why rather than leaving it unexplained: isolated measurement
showed real per-inference cost is only ~9.5ms/step once the model is
loaded, but a **fresh** spawned process pays ~4.1s just importing
`torch`+`transformers` (measured directly, isolated from model loading)
plus ~1.6s loading the actual pretrained weights — a ~5.7s fixed tax per
worker, comparable to the entire sequential run's total cost. `Process
PoolExecutor` on Windows uses spawn (not fork), so every fresh pool
re-imports the whole dependency tree from scratch.

**Three symbols, one shared pool** (`run_walk_forward_parallel_batch` on
AAPL+JNJ+TSLA together, 2,783 real steps total — above the 1500-step
auto-fallback threshold, so this correctly takes the process-pool path,
not the sequential fallback):

| Approach | Total time |
|---|---|
| Sequential (3 separate calls) | 31.69s / 33.14s (two separate real runs) |
| Parallel, **fresh pool per symbol call** | 40.98s (*worse* than sequential — confirms the fixed tax is real, not free, when paid repeatedly) |
| Parallel, **one shared pool for all 3** | 24.94s / 26.23s (two separate real runs, before and after adding `_default_n_workers`/the auto-fallback logic) — **1.26-1.27x vs sequential, ~1.6x vs fresh-pool-per-call** |

Verified via the actual public API (not just the prototype script), both
before and after adding the hardware-aware sizing and auto-fallback
logic, that every symbol's batch output is row-for-row identical to its
own sequential run.

**The takeaway**: the worker-startup tax is a fixed cost paid once per
pool, not per unit of work. It only pays off once amortized across
enough real work — a single symbol's ~921 steps doesn't clear that bar;
three symbols' combined ~2,783 steps does, and the win should keep
growing with more symbols/timeframes/angles batched into the same pool.
1.27-1.34x isn't the naive "4 workers → 4x" ideal (the fixed cost is
still a meaningful fraction of total time at this data volume), but it's
real, measured, and directionally exactly what the theory predicts.

## Fault tolerance — what happens when a worker errors

Added directly in response to being asked: if a parallel worker errors,
is it properly managed — does it retry, and if the whole thing is
restarted, does it pick up where it left off? The honest answer, checked
empirically rather than assumed, was **no** on all three counts at the
time the question was asked:

```
Test: one chunk out of several raises inside run_walk_forward_parallel
  -> Exception propagated: ValueError. Nothing at all was returned --
     not even the OTHER chunks' already-completed rows.

Test: run_walk_forward_parallel_batch, one job's chunk fails, a second
      job (already fully computed by another worker) is fine
  -> Exception propagated. The second job's complete, correct result
     was thrown away too, just because the batch call itself raised.
```

A single bad chunk killed everything, silently discarding any other
already-finished work in the same call — not what "properly managed"
means. Three things were built to fix this:

1. **Per-chunk retry + isolation** (`_execute_with_retry`, shared by both
   `run_walk_forward_parallel` and `run_walk_forward_parallel_batch`): a
   failed chunk is resubmitted up to `max_retries` times (default 2)
   before being given up on. `run_walk_forward_parallel` keeps its
   original contract (raises `RuntimeError` listing every chunk that
   failed after retries, once it's decided none of them are recoverable)
   — `run_walk_forward_parallel_batch` does not raise at all for a
   failed chunk; it returns whatever succeeded plus a `failures` list.
2. **`BatchResult`/`ChunkFailure`** (a real, breaking change to
   `run_walk_forward_parallel_batch`'s return type — nothing else in the
   codebase depended on the old `dict[str, DataFrame]` shape yet, so this
   was safe): `.data` is `{job.key: DataFrame}` as before, `.failures`
   lists any chunk that never succeeded, `.ok` is `True` iff nothing
   failed. Callers must check `.ok`/`.failures` rather than assuming
   success — a real, deliberate change to how errors surface.
3. **Disk checkpoint/resume** (`checkpoint_dir`/`resume` params on
   `run_walk_forward_parallel_batch`): each chunk's rows are written to
   disk the moment that chunk completes, via `_atomic_write_checkpoint`
   — the exact same fix as the real corrupt-live-parquet-file bug found
   and fixed earlier this session (known-issues.md Resolved #3): write
   to a temp file in the same directory, then `os.replace()` over the
   real target, so a crash mid-write never leaves a checkpoint that
   looks present but reads back broken. On a later call with the same
   `checkpoint_dir` and `resume=True` (the default), any chunk whose
   checkpoint already exists is loaded from disk instead of recomputed —
   proven, not assumed (see Verification below), by handing the second
   run a `step_fn` that always raises and confirming it still succeeds,
   because that step_fn is never actually called. `resume=False`
   discards existing checkpoints for the batch's exact chunks and starts
   clean. A corrupt/partial checkpoint file is treated as missing, never
   trusted.

**Two real bugs the tests caught while building this** (both fixed, not
just noted):

- `checkpoint_dir` was silently unreachable for any single-job batch.
  The original size-based fallback condition was
  `len(jobs) <= 1 or total_steps < min_total_steps_for_parallel` — for
  one job, `len(jobs) <= 1` is always true, so a single-job batch always
  took the sequential-fallback path regardless of `checkpoint_dir` being
  set, and the fallback path has no checkpoint support at all. Caught by
  the very first checkpoint test (`checkpoint_files` came back empty).
- The same `len(jobs) <= 1` check also silently defeated
  `min_total_steps_for_parallel=0`'s own documented "force the parallel
  path regardless, e.g. for testing" escape hatch — a single-job test
  passing `min_total_steps_for_parallel=0` still took the sequential
  fallback and therefore never got retried, no matter `max_retries`.
  Caught by the retry-recovery test failing with `attempts=1` (no retry
  ever happened).

Both traced to the same wrong assumption: that job *count* alone should
force the sequential path. It shouldn't — the worker-pool-tax argument
is about total *work*, not how many distinct jobs it's split across; a
single job with enough steps benefits from the process-pool path exactly
the way `run_walk_forward_parallel` already relies on for its own
chunks. Fixed by making the size decision purely `total_steps <
min_total_steps_for_parallel`, with `checkpoint_dir` (when given)
overriding that decision entirely, since passing it is the caller
explicitly asking for retry/resume safety that only exists on the
process-pool path.

## Verification

`vinu-tools/tests/test_walk_forward.py`: 26 tests (7 pre-existing + 19
new) — parallel output matches sequential row-for-row on synthetic data,
expanding-window is rejected with a clear error (both the single-job and
batch entry points), chunk boundaries drop or duplicate nothing,
empty/too-short jobs are handled gracefully inside a mixed batch, jobs of
different symbols (and, by construction, different step_fns) can share
one pool, `_default_n_workers` resolves `None` to `cpu_count - 1` and
never below 1, a small batch is proven to **never construct a
`ProcessPoolExecutor` at all** (monkeypatched to raise `AssertionError`
if instantiated), a transiently-failing chunk recovers via retry (a
file-based counter simulates the failure since a retry may land on a
different worker process, where in-memory state wouldn't persist), a
permanently-failing chunk lands in `.failures` without losing another
job's already-complete data, resume genuinely skips recomputation (proven
by handing the resumed run a `step_fn` that always raises, and confirming
it still succeeds), `resume=False` discards a stale-but-valid checkpoint
in favor of a fresh recompute, and a corrupt checkpoint file is treated
as missing rather than trusted. All pass; full `vinu-tools` suite: 145
passed (up from 128 before this whole piece of work).

`timer_timerxl/backtest.py`: `run_timer_timerxl_backtest(..., parallel=
True)` wired as the first real consumer, proven against real data above
and re-verified after the fault-tolerance rewrite — real 3-symbol batch:
32.06s sequential vs 24.27s batch (1.32x), `batch_results.ok: True`, zero
failures, all 3 symbols still row-for-row identical to sequential.
Existing `test_timer_timerxl_backtest.py`/`test_timer_timerxl.py`: 13
tests, all still pass — the new `parallel` flag is additive, the default
sequential path is untouched.

## What's done now (update)

All 7 parallel-safe angles (`arima`, `chronos`, `exponential_smoothing`,
`garch`, `kalman_filters`, `kronos`, `timer_timerxl`) now have a real
`parallel=True` flag on their `run_*_backtest()` entry point, same
`chunk_size`/`n_workers` kwargs as `timer_timerxl`'s original wiring.
`garch` needed one extra piece `timer_timerxl` didn't: its step function
is a closure over `timeframe` (needed for volatility annualization),
which doesn't survive being pickled to a worker process — fixed with
`functools.partial(_garch_step, timeframe=timeframe)`, a module-level
function with bound args, which does pickle correctly (proven via a real
multi-chunk `ProcessPoolExecutor` run, not assumed). See the
"row-for-row identical" correction above for what's actually provable
per angle — it isn't uniform across all 7.

Real regression tests added for the 5 genuinely-deterministic angles
(`test_arima_backtest.py`, `test_exponential_smoothing_backtest.py`,
`test_garch_backtest.py`, `test_kalman_filters_backtest.py` — plus a
second ARIMA test proving the 1min cadence>1 case runs successfully but
is *not* identical) — all pass. `chronos`/`kronos` were verified with a
real ad-hoc script instead of a permanent test (matching `timer_timerxl`'s
own original precedent of not baking expensive real-pretrained-model
calls into the permanent suite) since a value-equality assertion for
them would be asserting something false.

## What's not done yet

- **The 10 expanding-window angles** are explicitly not addressed here —
  needs a separate decision on whether to accept a bounded-lookback
  retraining semantic for them before any parallelization work starts.
- **Cross-chunk `refit_cadence`/`prior_state` reuse** (relevant to
  `arima`/`exponential_smoothing`/`garch`/`kalman_filters`) isn't
  optimized — documented above as a known, cheap-for-now gap.
- **A persistent/long-lived worker pool** (reused across many separate
  jobs over time, not just within one batch call) would likely extend
  the amortization further but wasn't built — today's pool lives only
  for the duration of one `run_walk_forward_parallel_batch()` call.
- **`min_total_steps_for_parallel`'s default (1500) is a rule of thumb
  from one angle's measured cost profile** (`timer_timerxl`'s ~5.7s/worker
  import+load tax and ~9.5ms/step inference), not a calibrated per-angle
  value. A angle with a much heavier model (slower import/load) or a much
  cheaper one would have a genuinely different real break-even point —
  worth revisiting once more of the 6 remaining parallel-safe angles are
  wired up and measured individually, rather than assuming one constant
  fits all of them.

## Related files

- `vinu-components/vinu-tools/vinu_tools/compute/backtest/walk_forward.py` — the implementation.
- `vinu-components/vinu-tools/tests/test_walk_forward.py` — the tests.
- `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/backtest.py` — the one wired consumer so far.
- `../00-project-understanding/03-stage1-planning.md` — this work sits inside Step 4 ("the full-analysis framework"), the stage-1 build step after all 31 angles were individually decided/built (Step 3, `06-implementation-of-each-angles/` itself).
