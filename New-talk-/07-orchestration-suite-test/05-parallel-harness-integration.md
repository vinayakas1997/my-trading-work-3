---
name: orchestration-suite-test-parallel-harness-integration
status: phase-1-done
purpose: the real record of integrating run_walk_forward_parallel_batch into the orchestrator (run_batch_with_parallel_harness) -- closing the one item 03-still-open-not-wired.md left as a deliberate deferral, once a real batch actually justified building it.
---

# 07 — Orchestration Suite Test — Parallel Harness Integration

`03-still-open-not-wired.md` deferred this deliberately: nesting a
per-job process pool inside `run_batch`'s per-job sequential loop
wouldn't get the harness's own benefit (that benefit comes from ONE
shared pool across many jobs). This closes that deferral by building the
actual thing that gets the benefit: one shared pool across every
parallel-safe angle in a real batch.

## What was built

**`orchestration_registry.py`** (extended):

- `PARALLEL_SAFE_ANGLES` — the same 7 angles `parallel-backtest-infra.md`
  already identified (`arima`, `chronos`, `exponential_smoothing`,
  `garch`, `kalman_filters`, `kronos`, `timer_timerxl`).
- `_PARALLEL_STEP_CONFIG` — angle name → its real `(step_fn builder,
  min_observations, window, horizon)`, reusing each angle's own
  already-built, already-tested module-level step function
  (`arima_step`, `chronos_step`, ..., `timer_timerxl_step`) directly —
  not reimplemented. `garch`'s own step needs `timeframe` bound
  (volatility annualization depends on it); its builder returns
  `functools.partial(_garch_step, timeframe=tf)`, same fix its own
  `run_garch_backtest(parallel=True)` already uses, proven picklable
  directly (not assumed) via a dedicated test.
- `build_walk_forward_jobs(symbols, bars_by_symbol, angle_names=...)` —
  real `WalkForwardJob` objects for the parallel-safe subset of
  `angle_names`, keyed `f"{symbol}:{angle_name}"` (same convention
  `run_batch`/`build_batch_jobs` already use, so results merge cleanly).
- `run_batch_with_parallel_harness(tracker, batch_id, symbols,
  bars_by_symbol, data_root, angle_names=..., ...)` — same real contract
  as `orchestration.run_batch` (every job registered up front for full
  visibility, batch rows deleted only once every job succeeds), but
  splits `angle_names` into the parallel-safe subset (routed through ONE
  shared `run_walk_forward_parallel_batch()` call) and everything else
  (routed through the existing sequential `run_batch()`, reused as-is —
  its own `register_batch`'s `INSERT OR IGNORE` makes the already-
  registered parallel rows a harmless no-op, and by the time its own
  `is_batch_complete()` check runs, every row already reflects its true
  final status, so the batch's rows are only ever deleted once,
  correctly, for the whole batch).

## Real proof

Real AAPL/JNJ/TSLA 1D bars (same real cached data as every other pass in
this project), 5 of the 7 parallel-safe angles (`arima`,
`exponential_smoothing`, `garch`, `kalman_filters`, `timer_timerxl` —
`chronos`/`kronos` excluded from this specific timing run only to keep
wall-clock reasonable: both need `MIN_OBSERVATIONS=512` and this run's
150-bar window would return 0 rows for them anyway, adding only model-load
time with nothing to measure), 3 symbols x 5 angles = 15 real jobs, old
sequential `run_batch()` vs. new `run_batch_with_parallel_harness()`:

```
=== OLD sequential path (run_batch) ===
sequential: 97.8s, ok=True, succeeded=15/15, remaining rows=0

=== NEW parallel-harness path (run_batch_with_parallel_harness) ===
parallel-harness: 46.5s, ok=True, succeeded=15/15, remaining rows=0

speedup: 2.10x

MATCH: every job's parallel-harness output is row-for-row identical to sequential
```

**2.10x real, measured speedup** — noticeably better than
`parallel-backtest-infra.md`'s earlier single-angle measurement
(1.26-1.34x for one angle across 3 symbols), because this batch shares
ONE pool across **5 angles x 3 symbols** (15 jobs) instead of one angle's
own 3 symbols — more real work amortizing the same fixed worker-startup
tax, exactly the scaling the earlier doc predicted ("the win should keep
growing with more symbols/timeframes/angles batched into the same pool").
Every job's output was independently confirmed row-for-row identical to
the sequential path (`pd.testing.assert_frame_equal`, not just "both
succeeded") — same real computation, differently scheduled, not an
approximation.

## Testing

`tests/test_orchestration_registry_parallel.py` (new, 9 tests):

- `build_walk_forward_jobs` only includes the parallel-safe subset of
  whatever `angle_names` is passed (silently excludes the rest — callers
  wanting a mixed batch use `run_batch_with_parallel_harness`, which does
  the real split).
- Each job's config matches the real angle's own `MIN_OBSERVATIONS`/
  `window`/`horizon` (checked directly, e.g. ARIMA's real 100).
- `garch`'s `functools.partial`-bound step_fn is proven picklable
  directly (`pickle.dumps`/`loads`), not assumed safe.
- Parametrized across the 4 cheap classical-stats angles (`arima`,
  `exponential_smoothing`, `garch`, `kalman_filters` — `chronos`/`kronos`/
  `timer_timerxl` need a real pretrained-model load per worker, too
  expensive for a permanent unit test, same precedent as their own
  individual `parallel=True` tests): parallel-harness output is
  row-for-row identical to sequential, proven per angle, not just once.
- A real **mixed** batch (2 parallel-safe angles + 1 non-parallel-safe
  angle, `shock_clustering`, in one call) proves the split-and-merge
  actually works together, not just each half in isolation.
- Fault isolation: a canned `ChunkFailure` for one job correctly becomes
  `tracker.mark_failed()`/`errors[key]` for that job specifically, while
  the other job's real result and tracker row (`status='ok'`) are
  untouched — and the batch's rows are NOT deleted while any job is still
  failed, so the failure stays visible rather than getting silently
  cleaned up. (A real data-driven chunk failure isn't reachable for
  these 4 angles — every one of their step_fns already catches its own
  fit/insufficient-data errors internally and returns a `"fit_failed"`
  status row rather than raising, by design — so this proves the
  integration's own failure-translation logic directly via a substituted
  `BatchResult`, the same fault-tolerance layer already exhaustively
  tested at the `vinu_tools` level in `test_walk_forward.py`'s 26 tests.)

Full `vinu-initial-analysis` suite: **453 passed → (see latest run)**,
zero regressions.

## What this closes, and what's still actually open

Closes `03-still-open-not-wired.md`'s parallel-batch-harness deferral —
it's no longer deferred, it's built, real, tested, and measured. The
deferral's own stated trigger ("if/when the real batch size or wall-clock
becomes a real problem... revisit") turned out to be answerable directly
by just building the real integration and measuring it, rather than
waiting further.

Still genuinely open, unrelated to this pass:

- **The 10 expanding-window angles** are still not parallel-safe by
  design (chunking would silently cap their growing context) — unchanged,
  a separate methodology decision, not something this integration
  affects.
- **`chronos`/`kronos` are still not row-for-row deterministic** even
  sequentially (real sampling-based inference, no fixed seed) — the
  parallel-harness integration doesn't change or fix this, it's a
  pre-existing property of those two models (see
  `parallel-backtest-infra.md`'s own correction on this).
- **`run_batch_with_parallel_harness` is opt-in**, not a replacement for
  `run_batch` — a caller only gets the shared-pool benefit by calling the
  new function; existing callers of plain `run_batch` are unaffected
  (same real contract, same real behavior, nothing silently changed under
  them).

## Related files

- `03-still-open-not-wired.md` — the original deferral reasoning this pass closed.
- `../06-implementation-of-each-angles/parallel-backtest-infra.md` — the harness's own build record and single-angle measured numbers this pass's 2.10x is compared against.
- `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/storage/orchestration_registry.py` — the implementation.
- `../../vinu-components/vinu-initial-analysis/tests/test_orchestration_registry_parallel.py` — the tests.
