---
name: implementation-of-each-angles-plan
status: decided
purpose: what this folder is for, how each angle actually gets implemented and proven, and the current status of all 31 — the execution phase that follows 04-enhancement-of-each-angle/'s decided designs and 05-storage-enhancement-levels/'s shared infrastructure.
---

# Implementation of Each Angle — Plan

## Why this folder exists

`04-enhancement-of-each-angle/` decided *what* every angle should become.
`05-storage-enhancement-levels/` built the shared machinery every angle's
backtest needs (tagging, the walk-forward loop, the weights store, the
query layer, clean deletion) and proved it end to end against real data
using DLinear. This folder is where that actually gets done for every
angle, one at a time, with a permanent record of what was touched, how it
was tested, and proof it works against real data — not just a status flag
flipped from "decided" to "built."

`Agents.md`, next to this file, is the step-by-step instruction set an
agent (or a future me, in a fresh session with no memory of this one)
follows to implement any one angle. This file is the overview and the
tracker; `Agents.md` is the actual how-to.

## Not every angle is the same shape of work

Reading back through `04-enhancement-of-each-angle/00-plan-and-status.md`
before writing this plan surfaced something worth stating plainly instead
of assuming every angle fits DLinear's mold: **most angles are point/
quantile forecasters that genuinely fit the walk-forward-loop-plus-
weights-store pattern DLinear proved, but several are not forecasters at
all**, and forcing them into `run_walk_forward`'s "one step, one forecast,
one weights file" shape would be wrong, not just extra work. Four groups:

- **Group A — walk-forward forecasters** (DLinear's pattern applies
  directly: `run_walk_forward` + `_tagging.tag_row` + weights store where
  a model is trained): `arima`, `chronos`, `dlinear` (done),
  `exponential_smoothing`, `garch`, `itransformer`, `kalman_filters`,
  `kronos`, `lag_llama`, `lpatchtst`, `lstm`, `moirai`, `moment`,
  `patchtst`, `tft`, `timer_timerxl`, `timesfm`,
  `tips_regime_aware_transformer`.
- **Group B — not forecasters** (their own decided designs describe
  aggregation, event-detection, or statistical-test output, not a
  step-by-step forecast; they still use tagging/storage/query, but not
  the point-forecast `step_fn` contract): `backtesting_44_metrics`,
  `news_price_causality`, `peer_relative_strength`, `pnl_attribution`,
  `regime_analysis`, `shock_clustering`, `shock_personality`,
  `trend_lifecycle`, `trend_session_structure`.
- **Group C — deferred, not implementable yet**:
  `cross_attention_gcn_news_price_fusion` — its own design doc says there
  is no real training loop yet; multi-ticker training is future work, not
  in scope here.
- **Group D — confirmed redundant, no work planned**: `ml_model_pipeline`,
  `news_first_analysis` — both already flagged in
  `04-enhancement-of-each-angle/00-plan-and-status.md` as superseded by
  other, already-covered code. Not implemented here; folders exist only
  to record that decision, not an implementation.

`Agents.md` has the full 31-row table with each angle's group, so an agent
picking up any one angle knows immediately which shape of work it's
signing up for before reading further.

## Per-angle folder structure

Each angle gets its own folder here, `{NN}-{angle-name}/`, numbered the
same way `04-enhancement-of-each-angle/` already numbers them (so `01-arima/`
here corresponds to `04-enhancement-of-each-angle/01-arima.md`). A folder
is only created once real implementation work on that angle actually
starts — not as an empty placeholder for all 31 up front, since its files
need real content (real files touched, real bugs found) that doesn't
exist before the work happens. Inside each:

- **`01-implementation.md`** — the full record: which real files were
  touched (and how — new file vs. edit), how it was implemented (the
  actual approach, not a copy of the design doc), what was tested and how,
  and any bugs found along the way (including ones found and fixed during
  implementation itself, the way the `weights_sink` argument-mismatch bug
  was caught while reviewing `05-storage-enhancement-levels/plan.md`).
- **`02-real-scenario.md`** — one concrete, real example proving it
  actually works: a real API/function call, real input data (a small
  sample, not fabricated numbers), and the real output that came back —
  the same kind of proof `05-storage-enhancement-levels/angle-validation-checklist.md`
  requires (real market data, not synthetic), just written up as a
  readable example instead of left as terminal output.

`05-dlinear/` is the first instance of this pattern — it exists already,
written from the real implementation and real-data validation work done
in `05-storage-enhancement-levels/`.

## Definition of done, per angle

An angle isn't marked done in the status table below until all of these
are true:

1. Code written (backtest glue file, and any small refactor to expose
   what the shared infrastructure needs — e.g. DLinear's `compute.py`
   split so the trained model could be handed to the weights store).
2. Unit tests written and passing, in the same style as the existing
   tests (real objects, temporary folders, no mocking).
3. The real-data validation checklist
   (`05-storage-enhancement-levels/angle-validation-checklist.md`) run and
   passed for **Phase 1: the coarsest 1-2 timeframes the angle
   declares** (see `Agents.md`'s "Two-phase timeframe checking") — real
   data fetched from Alpaca (1-minute bars, aggregated to whichever
   timeframe is needed), ~6 months, AAPL (+ SPY for any cross-symbol
   angle), including the API round-trip check (write, read back, query).
   The remaining declared timeframes are **Phase 2, deferred** — tracked
   per angle in its own `01-implementation.md`, not silently skipped, and
   picked up in a later pass across all angles once Phase 1 is done for
   all of them.
4. The full project test suite run for both `vinu-initial-analysis` and
   `vinu-tools`, confirming no new failures (pre-existing, already-flagged
   failures like `shock_clustering`/`shock_personality`'s `bar_ts` bug
   don't block this — they're tracked separately, not part of this work).
5. `{NN}-{name}/01-implementation.md` and `02-real-scenario.md` written.
6. The status table below updated (note "Phase 1" vs "Phase 1+2" in the
   status column so timeframe coverage is visible at a glance).

## Build order

**Decided (revised): strict numeric folder order, angle by angle** — `01`
through `31`, not grouped by Group A/B as originally planned. `dlinear`
(05) was already done first to prove the shared infrastructure works at
all; from `01-arima` onward, the order is just the numbered list, skipping
only:
- Group C (`04-cross_attention_gcn_news_price_fusion`) — deferred, no
  training loop exists to build against.
- Group D (`15-ml_model_pipeline`, `18-news_first_analysis`) — confirmed
  redundant, no work planned.
- `05-dlinear` — already done.

Whatever group an angle falls into (see "Not every angle is the same
shape of work" above) still determines *how* it's implemented once its
turn comes up — the walk-forward pattern for Group A, the looser
tagging/storage/query-only pattern for Group B — this section only
changed *which order* angles get picked up in, not how each one is built.

## Known issues found during implementation (not yet fixed)

Bugs found while implementing one angle sometimes turn out to be shared
(a `vinu_tools` function another angle also depends on) or bigger than a
same-turn fix warrants. Those are tracked separately in
[known-issues.md](known-issues.md), not just inside the angle that found
them, so they stay discoverable and can be combined/prioritized in their
own dedicated pass later rather than getting buried or fixed piecemeal.

## Performance — parallel walk-forward execution

ARIMA's real-data validation showed the actual bottleneck for any
angle that fits a statistical/ML model per step isn't the shared harness
or pandas — a single ARIMA grid-search fit is ~0.53s and that's almost
entirely inside `statsmodels`' own compiled fitting code, not Python
overhead. The real lever: **parallelize refit steps across CPU cores** —
each refit step's fit depends only on its own rolling window (only the
cheap `.append(refit=False)` steps are sequential), so refits are
embarrassingly parallel. **Now built and real-data-validated** — see
[parallel-backtest-infra.md](parallel-backtest-infra.md) for the shared
`run_walk_forward_parallel`/`run_walk_forward_parallel_batch` harness,
the 7-angle/10-angle/13-angle group split (which angles are safe to
parallelize as-is), the real measured speedup (1.26-1.34x on a real
3-symbol batch), and the fault-tolerance layer (retry, error isolation,
disk checkpoint/resume) built on top of it. `timer_timerxl` is the one
angle actually wired to it so far; the other 6 parallel-safe angles are
mechanical follow-up work, not a new design question.

## Adding a new angle

[adding-a-new-angle.md](adding-a-new-angle.md) — the guide for adding
angle #32 and beyond: the config/env-override pattern
(`get_angle_setting()`), which walk-forward pattern to use, the
real-data-validation bar every one of the 31 existing angles was held
to, and a checklist.

## Status table

| # | Angle | Group | Folder | Status |
|---|---|---|---|---|
| 01 | arima | A | [01-arima/](01-arima/) | done (all 6 timeframes) |
| 02 | backtesting_44_metrics | B | [02-backtesting_44_metrics/](02-backtesting_44_metrics/) | phase-1-done (1D; 5min/15min/1H/4H/1min Phase 2 deferred; 1W/1M/6M intentionally excluded from the rolling backtest) |
| 03 | chronos | A | [03-chronos/](03-chronos/) | phase-1-done (1H, 9 real steps — 1D infeasible, needs 512 real bars, only 125 available; 1min/5min/15min/4H Phase 2 deferred) |
| 04 | cross_attention_gcn_news_price_fusion | C | — | deferred (no training loop) |
| 05 | dlinear | A | [05-dlinear/](05-dlinear/) | phase-1-done (1D only; 5 timeframes were missing from spec.yaml, found and fixed during angle 02 — 1min/5min/15min/1H/4H are Phase 2, deferred) |
| 06 | drawdown_deep_dive | B | [06-drawdown_deep_dive/](06-drawdown_deep_dive/) | phase-1-done (1D, 3 real episodes + real k-sweep; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 07 | exponential_smoothing | A | [07-exponential_smoothing/](07-exponential_smoothing/) | phase-1-done (1D; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 08 | garch | A | [08-garch/](08-garch/) | phase-1-done (1D; found+fixed a real annualization bug; found+documented, then fixed in a dedicated cross-angle pass, an upstream `vinu_tools` omega-estimator bug shared with shock_personality — see known-issues.md Resolved #2; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 09 | itransformer | A | [09-itransformer/](09-itransformer/) | phase-1-done (1D; fixed a real gap — all 5 channel forecasts now exposed, not just close; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 10 | kalman_filters | A | [10-kalman_filters/](10-kalman_filters/) | phase-1-done (1D — first angle to beat its naive baseline, 60% vs 52%; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 11 | kronos | A | [11-kronos/](11-kronos/) | phase-1-done (1H, 9 real steps, same window as Chronos for a fair side-by-side; 1min/5min/15min/4H + 1D Phase 2 deferred, 1D likely infeasible at 6mo like Chronos) |
| 12 | lag_llama | A | [12-lag_llama/](12-lag_llama/) | phase-1-done (1D, 21 real steps, 90%→71% CI-coverage decay across the 5-step horizon; only the real-weights path is deferred, not the fallback-proxy backtest itself — corrected out of order, built after 13/14; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 13 | lpatchtst | A | [13-lpatchtst/](13-lpatchtst/) | phase-1-done (1D, 48% vs corrected 57.7% paper benchmark; fixed a stale ~54% miscitation in spec.yaml; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 14 | lstm | A | [14-lstm/](14-lstm/) | phase-1-done (1D, 44% vs corrected 55.4% paper benchmark; found a real corrupt-live-parquet-file bug blocking all AAPL queries — worked around at the time, since fixed for real in a dedicated pass (known-issues.md Resolved #3); 1min/5min/15min/1H/4H Phase 2 deferred) |
| 15 | ml_model_pipeline | D | — | no work planned (redundant) |
| 16 | moirai | A | [16-moirai/](16-moirai/) | phase-1-done (1D, 21 real steps, 90%→33% CI-coverage decay — faster than lag_llama's on identical data, a real finding about the proxy's calibration at longer horizons; only the real-weights path is on hold, not the fallback-proxy backtest itself; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 17 | moment | A | [17-moment/](17-moment/) | phase-1-done (1D, 21 real steps, 86%→67% CI-coverage; real-weights wiring is a settled "no" per its design doc, not deferred; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 18 | news_first_analysis | D | — | no work planned (redundant) |
| 19 | news_price_causality | B | [19-news_price_causality/](19-news_price_causality/) | phase-1-done (1min impact rows + 1D-bucket quarter-aggregate tests; 156 real AAPL articles, only 2023-Q1 clears the sample floor, Granger not significant (p=0.279); found a real cross-cutting data gap — finbert_score always NULL — since fixed by backfilling real FinBERT scores (known-issues.md Resolved #4); significance classifier still doesn't train, now for a real, separate reason (only 5 ar_significant positives in the real news window, below the 10+3 floor); remaining timeframes N/A per design — Granger/correlation/lag always operate on hourly-resampled data regardless of requested timeframe) |
| 20 | patchtst | A | [20-patchtst/](20-patchtst/) | phase-1-done (1D, 44% vs lpatchtst's 48% on identical real data — the ablation comparison this angle exists for; benchmark citation already correct, no fix needed; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 21 | peer_relative_strength | B | [21-peer_relative_strength/](21-peer_relative_strength/) | phase-1-done (1D, real AAPL vs TSLA/JNJ, 394 rows + 32 forward-return-validation buckets; weak, inconsistent-direction hint at 20d horizon (7/48 independent tests p<0.05, corrected after angle 24's pearson_with_ci CI fix); added shared `pearson_with_ci`/`calendar_quarter_key` helpers; found a 2nd corrupt-parquet-file instance (JNJ) confirming the pattern was systemic — since fixed for real, known-issues.md Resolved #3) |
| 22 | pnl_attribution | B | [22-pnl_attribution/](22-pnl_attribution/) | phase-1-done (by_artifact_id breakdown added; no real production trade data exists yet — design doc's own stated fact, not a gap found here; validated against schema-accurate positions + the real ingest/storage round-trip instead) |
| 23 | regime_analysis | B | [23-regime_analysis/](23-regime_analysis/) | phase-1-done (fixed a real, confirmed look-ahead leak in the vol threshold — adopted regime_features.py's already-validated rolling z-score; added per-bar rows + quarterly breakdown + normalized transition_prob; real AAPL: bull 46.4% Sharpe 3.20, bear 23.3% Sharpe -1.86) |
| 24 | shock_clustering | B | [24-shock_clustering/](24-shock_clustering/) | phase-1-done (fixed 2 confirmed bugs — gap-trigger leak + fake shock-conditioning; real AAPL/TSLA shock-day corr 0.595 CI[0.41,0.74] vs AAPL/JNJ 0.167 CI[-0.05,0.36]; found+fixed a real pearson_with_ci bootstrap-CI bug, retroactively corrected angle 21's docs; resolves 3 of 11 pre-existing bar_ts test failures) |
| 25 | shock_personality | B | [25-shock_personality/](25-shock_personality/) | phase-1-done (fixed 3 confirmed bugs — gap-trigger leak + 2 computed-then-discarded fields now surfaced; real AAPL: GARCH persistence 0.973 (updated after known-issues.md Resolved #2's omega fix), post-shock autocorr -0.051 CI[-0.06,-0.04]; resolves the remaining 8 of 11 pre-existing bar_ts test failures — all 11 now fixed) |
| 26 | tft | A | [26-tft/](26-tft/) | phase-1-done (1D, 36% hit-rate vs corrected 58.4% benchmark, 68% CI-coverage vs nominal 80%; benchmark citation already correct, itransformer cross-check already closed in design doc; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 27 | timer_timerxl | A | [27-timer_timerxl/](27-timer_timerxl/) | phase-1-done (1D, FULL real history — 921 real steps, largest real sample this session; ~50% hit rate, ~73% coverage vs nominal 80%; fixed a real MIN_OBSERVATIONS/patch-size mismatch + a stale "(fallback proxy)" spec.yaml doc bug; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 28 | timesfm | A | [28-timesfm/](28-timesfm/) | phase-1-done (1D, 196 real steps; coverage 88%→80% — best-calibrated quantile angle this session, nearly matches its own nominal 80% target; fixed 2 confirmed gaps — 256→1024 context, 7-of-10 discarded deciles now kept; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 29 | tips_regime_aware_transformer | A | [29-tips_regime_aware_transformer/](29-tips_regime_aware_transformer/) | phase-1-done (1D, 250 real bars/130 steps for regime diversity; momentum 50.5% vs mean_reversion 51.7% hit rate — regime-gating doesn't clearly earn its keep on this sample, honest finding; benchmark correctly not carried over from the unrelated cited paper; 1min/5min/15min/1H/4H Phase 2 deferred) |
| 30 | trend_lifecycle | B | [30-trend_lifecycle/](30-trend_lifecycle/) | phase-1-done (signal-outcome backtest + confidence calibration added; real AAPL: 16 real peaks, 6 book_profits signals, calibration inconclusive at n=3/bucket; fixed confirmed 1W spec.yaml gap; found a 3rd instance of the table/prose timeframe-widening doc inconsistency) |
| 31 | trend_session_structure | B | [31-trend_session_structure/](31-trend_session_structure/) | phase-1-done (per-session confidence-calibration breakdown added; confirmed already bug-free, no correctness work needed; real check on 1D data structurally collapses to one session as expected, real intraday breakdown deferred to Phase 2; widened to include 1min/5min, 1D correctly stays excluded) |

## Related files

- `Agents.md` — the actual step-by-step instructions for implementing one
  angle, plus the full per-angle lookup table (design doc path, code path,
  declared timeframes).
- `04-enhancement-of-each-angle/00-plan-and-status.md` — the decided
  design for every angle; source of truth for *what* to build.
- `05-storage-enhancement-levels/plan.md` — the shared infrastructure
  every Group A angle's implementation reuses.
- `05-storage-enhancement-levels/angle-validation-checklist.md` — the
  real-data checklist every angle must pass before being marked done here.
