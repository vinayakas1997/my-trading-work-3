---
name: orchestration-suite-test-still-open
status: fully-superseded
purpose: originally tracked 4 unwired-but-built angles plus the parallel-batch-harness deferral. All 4 angles were wired (04-extra-data-angles-wired.md) and the parallel-batch harness is now integrated for real (05-parallel-harness-integration.md) — nothing on this page is still open. Kept as the original record of why each item needed what it needed, since that reasoning is what each fix actually solved.
---

# 07 — Orchestration Suite Test — Still Open (not wired into the registry)

**Update**: everything on this page is resolved. All 4 angles below are
wired into the registry — see `04-extra-data-angles-wired.md` for what
was built (a local price-client adapter, real news fetching per symbol,
an inline-chained call for `trend_session_structure`, and for
`pnl_attribution` — installing `vinu-live` editable so its real
`BookBackend`/`list_closed_positions` became importable at all, then a
new `"positions"` shape) and the real proof for each. The parallel-batch
harness deferral below is also resolved — see
`05-parallel-harness-integration.md`: `run_batch_with_parallel_harness()`
shares one process pool across every parallel-safe angle in a batch, real
measured **2.10x speedup** on a real 15-job batch, row-for-row identical
to sequential. The sections below are kept as the original record of
*why* each item needed what it needed — that reasoning is what each fix
actually solved, so it's still worth reading, not stale.

## The 4 angles (original record — all 4 now resolved, see above)

### `news_price_causality` — built, needs real extra data to be meaningful

- **Real entry points**: `run_impact_backtest(symbol, candles, articles)`,
  `run_aggregate_tests_backtest(symbol, candles, articles)`.
- **Real-validated**: 156 real AAPL-linked articles (vinu-news's cached
  `news.db`) against real 1-minute AAPL bars — 268 real impact rows, a
  real (non-significant, p=0.279) Granger-causality result on the one
  quarter with enough sample size. Storage/query round-trip confirmed.
- **Why not in the registry**: `articles` is a **required positional
  argument**, not optional — there is no bars-only call shape for this
  angle. The registry's `build_batch_jobs()` only threads
  `(symbol, bars, data_root)` through; wiring this angle in would mean
  either fetching real news articles per symbol as part of the batch
  (a real, separate data-assembly step) or accepting an empty/fake
  `articles` list, which would silently produce a meaningless result
  rather than the honest "insufficient data" the angle already reports
  when given real-but-thin data.
- **What "wiring it in" actually requires**: extending `build_batch_jobs`
  (or a parallel batch-builder) to also fetch `articles` per symbol from
  vinu-news before building the job closure — not a code change to the
  angle itself.

### `peer_relative_strength` — built, needs a real peer-price feed to be meaningful

- **Real entry points**: `run_relative_strength_backtest(symbol, bars,
  price_client=...)`, `run_forward_return_validation(symbol, bars,
  price_client=...)`.
- **Real-validated**: real AAPL vs. real TSLA/JNJ peers, full 1025-day
  real history — 394 relative-strength rows, 32 forward-validation
  buckets, a real (weak, inconsistent-direction) forward-return finding
  after the bootstrap-CI bug fix. Storage/query round-trip confirmed.
- **Why not in the registry**: confirmed **directly, not assumed** — it
  runs without a `price_client` but only ever returns a hollow
  `status: "no_peers"` row in that case. A `price_client` giving it real
  peer prices is required for the angle to produce anything but a
  placeholder. The current registry has no notion of "this symbol's
  peers" or a shared `price_client` to inject.
- **What "wiring it in" actually requires**: the batch builder would need
  a peer-symbol map (e.g. AAPL → [JNJ, TSLA]) and a shared `price_client`
  instance threaded into the job closure — a real design decision (who
  defines peer groups for which symbol), not just a registry entry.

### `trend_session_structure` — built, depends on another angle's own output

- **Real entry point**: `aggregate_signal_outcomes_by_session(signal_outcomes)`
  — takes `trend_lifecycle`'s own `run_signal_outcome_backtest(...)` output
  as its input, not raw bars.
- **Real-validated**: real AAPL 1D `trend_lifecycle` signal-outcomes fed
  through — correctly returns `not_applicable` on 1D (every peak lands in
  the same session bucket, a real structural property this angle's own
  design doc predicted, not a bug), with the aggregation/join logic
  confirmed correct via matching `trend_lifecycle`'s own unsliced
  aggregate exactly when every row shares one session.
- **Why not in the registry**: it isn't a `(symbol, bars) → result` angle
  at all — it's a `(trend_lifecycle's own result) → result` angle. The
  registry's job model is "one angle, one symbol, one bars slice";
  running this for real means running `trend_lifecycle` first, feeding
  its actual output in, which is a two-step in-batch dependency the
  current scheduler (`run_batch` runs every job independently, any order)
  doesn't support.
- **What "wiring it in" actually requires**: either (a) a dependency edge
  in the job graph (`trend_session_structure`'s job waits for
  `trend_lifecycle`'s job on the same symbol to finish, then reads its
  result), or (b) special-casing it to run its own internal
  `trend_lifecycle` call first. (a) is the more correct fix if any other
  angle ever needs the same pattern; not designed yet.

### `pnl_attribution` — built, genuinely different input shape (trade data, not bars)

- **Real entry point**: `aggregate_pnl_attribution(symbol, positions)` —
  `positions` is closed-trade data (`position_id`, `side`, `qty`,
  `avg_entry`, `realized_pnl`, `artifact_id`, ...), matching the real
  `vinu-live` `Position` schema exactly, not `bars`.
- **Real-validated**: schema-faithful 3-position example — correct
  per-`artifact_id` P&L grouping (which trading plan is making money),
  correct `insufficient_sample` flagging at n=1-2, and a real
  ingest→storage→read round-trip through the actual production path
  (`pnl_attribution_ingest.py`), not a test shortcut.
- **Why not in the registry**: there is no real Phase 6 (live trading)
  closed-position data in this project yet — stated in the angle's own
  design doc as an open item, not discovered here. Even if the registry
  supported a `positions`-shaped job (it doesn't — every current shape
  takes `bars`), there's no real data to run it against today.
- **What "wiring it in" actually requires**: real closed-trade data
  existing first (a live-trading/paper-trading milestone, unrelated to
  this orchestrator), then a genuinely new job shape (`positions` instead
  of `bars`) — not a gap in this pass's work, a dependency on a future
  milestone.

## Is deferring the parallel-batch harness integration OK? (original reasoning — now resolved, see below)

**Original answer: yes — this one's a reasoned "not yet," not a gap.** Reasoning:

- `run_walk_forward_parallel_batch` (in `vinu_tools/compute/backtest/walk_forward.py`)
  already exists, is unit-tested (26 tests: parallel correctness, retry,
  checkpoint/resume), and its own measured numbers
  (`06-implementation-of-each-angles/parallel-backtest-infra.md`) show it
  only pays off at real batch scale — a single job saw **no gain** (1.02x,
  process-spawn overhead eats the benefit), a 3-symbol batch saw a modest
  1.26–1.34x.
- `run_batch`'s current design runs each `(symbol, angle)` job
  **sequentially, one at a time, in-process** — the real 72-job run
  finished in 398.8s (~5.5s/job average) with zero failures. There's no
  observed pain point (timeout, user complaint about wall-clock) that
  parallelizing would fix right now.
- Nesting the parallel-batch harness inside `run_batch`'s per-job loop
  wouldn't get the harness's own benefit anyway — that benefit comes from
  **one shared process pool across many jobs**, not from parallelizing
  the internal steps of a single job while jobs themselves stay
  sequential. Wiring it in "for completeness" without that redesign would
  add real complexity (process-pool lifecycle, checkpoint paths, retry
  semantics layered on top of `run_batch`'s own retry) for no measured
  benefit.
- The honest trigger to actually do this: if/when the real batch size
  or wall-clock becomes a real problem (many more symbols, or the 7
  extra dependent/extra-data angles above all landing in the same batch),
  revisit — at that point `run_batch` would call
  `run_walk_forward_parallel_batch` per angle-group instead of looping
  jobs one at a time. Not designed yet because there's no real number
  yet showing it's needed.

**Update — resolved**: built for real. `run_batch_with_parallel_harness()`
now exists (`orchestration_registry.py`), sharing one process pool across
every parallel-safe angle in a batch — measured **2.10x** on a real
15-job batch (5 angles x 3 real symbols), row-for-row identical to
sequential. See `05-parallel-harness-integration.md` for the full build
record, the real numbers, and the 9 new tests. `run_batch` itself is
unchanged (still the plain sequential path, still used by every existing
caller) — `run_batch_with_parallel_harness` is a new, opt-in function a
caller reaches for when it wants the shared-pool benefit.

## Related files

- `plan.md` — the original classification these 4 angles were scoped out
  of, including the corrected reasoning found when directly asked "why
  weren't the other angles considered."
- `01-implementation.md` / `02-real-scenario.md` — the 24-angle registry
  build record and real 72-job proof this doc's 4 exclusions are scoped
  against.
- `04-extra-data-angles-wired.md` — the real record of wiring in all 4 angles from this page.
- `05-parallel-harness-integration.md` — the real record of building and measuring `run_batch_with_parallel_harness()`, resolving the deferral this page originally recommended.
- `../06-implementation-of-each-angles/19-news_price_causality/`,
  `21-peer_relative_strength/`, `31-trend_session_structure/`,
  `22-pnl_attribution/` — each angle's own real implementation + real-scenario record.
- `../06-implementation-of-each-angles/parallel-backtest-infra.md` — the
  parallel-batch harness's own single-angle measured numbers this page's
  original deferral reasoning was based on.
