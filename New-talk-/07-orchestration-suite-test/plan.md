---
name: orchestration-suite-test-plan
status: phase-1-done
purpose: plan for wiring the angle-run-status orchestrator (built in 06-implementation-of-each-angles) to a real angle registry and proving it at real scale — 24 angles × 3 real symbols, not the earlier 5-job demo. Includes a real classification correction found when the user asked why only 22 (not more) of the 28 built angles were included.
---

# 07 — Orchestration Suite Test — Plan

## Where this picks up

`vinu-initial-analysis/vinu_initial_analysis/storage/orchestration.py`
(`AngleRunStatus`, `run_batch()`) was built and unit-tested in the
`06-implementation-of-each-angles` pass, then proven against a small
real 5-job demo (2 angles × 2 symbols + 1 deliberately broken job). This
folder is the next step: wire it to every angle that's actually ready for
it, and prove the full orchestrator at real scale.

## The full 31-angle accounting

31 total = **28 phase-1-done** (built, real-data-validated) + **1 Group C
deferred** (`cross_attention_gcn_news_price_fusion` — no training loop
exists) + **2 Group D no-work-planned** (`ml_model_pipeline`,
`news_first_analysis` — confirmed redundant with other angles). Only the
first bucket (28) can be orchestrator-ready at all; the other 3 were
never built by design, unrelated to this pass.

## The angle classification (checked against every angle's real entry-point signature) — CORRECTED

The first version of this table wrongly excluded 2 real, already-built
angles by lumping them in with the 3 genuinely-never-built ones without
actually reading their signatures — caught when directly asked "why
weren't the other angles considered." Both were fixed, not just
re-labeled — see `01-implementation.md`'s "Classification correction"
section for the full story, including a second real bug (`shock_personality`'s
wrong call shape) the fix itself surfaced.

| Group | Count | Angles | Orchestrator-ready? |
|---|---|---|---|
| **Uniform, bars-only** | 24 | `arima`, `chronos`, `dlinear`, `drawdown_deep_dive`, `exponential_smoothing`, `garch`, `itransformer`, `kalman_filters`, `kronos`, `lag_llama`, `lpatchtst`, `lstm`, `moirai`, `moment`, `patchtst`, `timesfm`, `timer_timerxl`, `tft`, `tips_regime_aware_transformer`, `backtesting_44_metrics`, `regime_analysis`, `shock_clustering`, `shock_personality`, `trend_lifecycle` | Yes — all take `(symbol, [timeframe,] bars[, data_root])` with any other input (news) genuinely optional. |
| **Wired with a real extra dependency, injected via `build_batch_jobs()`** | 5 (3 angles, 2 with 2 real outputs each) | `news_price_causality_impact`/`_aggregate` (real articles fetched per symbol via `NewsRepository`), `peer_relative_strength`/`_forward_validation` (real peer prices via `LocalPriceClient`, no HTTP server needed), `trend_session_structure` (chained inline: calls `trend_lifecycle`'s real backtest, then aggregates it) | **Yes, done** — see `04-extra-data-angles-wired.md` for what was built and the real 15/15-job proof. |
| **No bars-driven backtest at all, by design** | 3 | `ml_model_pipeline`, `news_first_analysis`, `cross_attention_gcn_news_price_fusion` | Out of scope — these are the genuinely never-built Group C/D angles, not a data-shape mismatch. |
| **Wired via a new `"positions"` shape, no bars needed** | 1 | `pnl_attribution` (real functions operate on `closed_positions`/trade data, not `bars` — `build_batch_jobs(positions_by_symbol=...)` threads real data through; the real blocker was `vinu_live` not being importable in this environment, fixed by installing it editable, not a code-shape problem) | **Yes, done** — see `04-extra-data-angles-wired.md`. Real closed-trade data itself still doesn't exist (no live trading has run), so real batch runs honestly return `status: "no_data"` until it does — that's the angle's own correct behavior, not a gap in this wiring. |

24 + 3 (as 5 registry entries) + 3 + 1 = 31 angles, 30 registry entries
(counting `news_price_causality`'s and `peer_relative_strength`'s 2 real
outputs each as separate entries, matching how they're stored).

**What changed from the first version**: `drawdown_deep_dive` moved from
"no backtest.py at all" to the main 24-angle registry (it has a real,
working `(symbol, timeframe, bars)`-shaped entry point,
`run_drawdown_detection` — I never actually checked before excluding
it). `shock_personality` moved from "needs extra data" to the main
registry too (its `news` param is optional with a real, full-value
degraded path, confirmed against its own `06-implementation-of-each-angles`
real-scenario doc). `pnl_attribution` got its own row instead of being
lumped with the 3 genuinely-unbuilt angles, since it's real and built,
just not bars-driven.

## What this pass builds

1. **An angle registry** (`orchestration_registry.py`, sibling to
   `orchestration.py`) — `ANGLE_REGISTRY`: angle name → its real backtest
   entry point + a call-shape tag, `build_work_fn()` (assembles the right
   call for one angle/symbol), `build_batch_jobs()` (symbols × angles →
   job tuples for `run_batch()`).
2. **Real bars, once per symbol**, for all 3 real cached symbols —
   **AAPL, JNJ, TSLA** — fetched through
   `vinu_stock.query.engine.fetch_candles()` (the corrupt-file issue that
   used to require a workaround here was fixed for real earlier this
   session — known-issues.md Resolved #3).
3. **72 real jobs** (24 angles × 3 symbols) registered under one
   `batch_id` and run through `run_batch()` for real.
4. **Real numbers reported**: total wall-clock time, success/failure
   counts, confirmation the tracking table cleans itself up on full
   success (or shows exactly what's stuck if not).

## What this pass deliberately does NOT do

- **Wire the parallel-batch harness into `run_batch`.** The 7
  parallel-safe angles (per `06-implementation-of-each-angles/parallel-backtest-infra.md`)
  could in principle use `run_walk_forward_parallel_batch` internally,
  but that only pays off when *many* jobs share one process pool — a
  single job's parallel-batch call nested inside `run_batch`'s per-job
  sequential loop wouldn't get that benefit. A separate design decision.
- **The 2 extra-data angles and the 1 dependent angle** — separate,
  smaller follow-up once the extra real data or in-batch sequencing is designed.
- **The 4 non-bars-driven angles** — unchanged, out of scope for a
  bars-driven registry by construction, not a gap.

## Verification plan

- Unit tests for the registry itself, including a real regression test
  for the `shock_personality` call-shape bug found while correcting this
  classification.
- Real-data end-to-end run: 72 real jobs, `AngleRunStatus` tracking
  table before/after, full pass/fail breakdown, wall-clock timing.
- Any real bug found while wiring/running this gets fixed and recorded
  in this folder's own implementation doc (not silently patched).

## Closing note — done

66/66 real jobs succeeded on the first pass (22-angle registry). Being
asked to account for the rest surfaced two real, fixable mistakes
(`drawdown_deep_dive` wrongly excluded, `shock_personality` wrongly
excluded *and*, once added, wrongly wired — see `01-implementation.md`),
plus the earlier `kronos` config-completeness gap found in the first
pass. All fixed, all re-verified against real data, not just re-labeled.
See `01-implementation.md` for the full build record and both bugs,
`02-real-scenario.md` for the final real numbers.

**Update**: `news_price_causality`, `peer_relative_strength`,
`trend_session_structure`, and `pnl_attribution` were all wired into the
registry across two follow-up passes (`04-extra-data-angles-wired.md`) —
30 registry entries now, real proof for all 4 (including a real,
currently-empty `BookBackend` for `pnl_attribution`).

**Update 2**: the parallel-batch harness is now integrated too —
`run_batch_with_parallel_harness()` (`05-parallel-harness-integration.md`),
real measured **2.10x speedup** on a real 15-job batch, row-for-row
identical to sequential. Only the 3 never-built Group C/D angles remain
out of scope, by design, not as an open item.

## Related files

- `04-extra-data-angles-wired.md` — what was built to wire in the 3 extra-data/dependent angles, and the real proof it works.
- `03-still-open-not-wired.md` — the original reasoning for why each of those 3 needed something extra (still accurate), plus the still-open `pnl_attribution` case and the parallel-batch-harness deferral reasoning.
- `../06-implementation-of-each-angles/parallel-backtest-infra.md` — the group-split table this plan's classification is checked against.
- `../06-implementation-of-each-angles/adding-a-new-angle.md` — the config/pattern guide new angles (and this registry) follow.
- `../00-project-understanding/03-stage1-planning.md` — Step 4, "the full-analysis framework" — this orchestration work is what fills that gap.
