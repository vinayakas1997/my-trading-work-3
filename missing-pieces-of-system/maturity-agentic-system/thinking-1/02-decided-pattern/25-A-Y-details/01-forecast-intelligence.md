# Cluster 1 — Forecast Intelligence: A, Q, P, G, S

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

---

## A. Angle trust trajectories

**Source stores**: `angle_calibration_entries` (vinu-research
`strategy_store.py`: `id, angle_name, artifact_id FK, forecast_direction,
actual_return_pct, forecast_magnitude_pct, brier_score,
directional_correct, magnitude_error, timestamp`) · `decay_snapshots`
(`artifact_id FK, evaluation, ic_ratio, rolling_ir, ic_positive_ratio,
rolling_sharpe, n_entries, timestamp`) · `ticker_daily_snapshots`
(`ticker, snapshot_date, angle_digest JSON, angles_with_data,
angle_count`) · `artifacts.regime_tag`, `artifacts.universe`.

**Fetch**: for each `angle_name`, pull every `angle_calibration_entries`
row ordered by `timestamp`, joined via `artifact_id` to
`artifacts.regime_tag` (for the regime breakdown) and
`artifacts.universe` (for the ticker-cluster breakdown).

**Condition**: this angle's trailing-30-entry mean `brier_score` moves
outside its own trailing-90-entry P10/P90 band — computed fresh from
`angle_calibration_entries` every cycle, not from any gated row. Also
checked against the domain floor `brier_score ≥ 0.5` (worse than random)
as an absolute trigger regardless of trend. The same P10/P90 test is run
separately per `regime_tag` bucket for the regime-conditioned view.

**Storage**: `scope_type=angle`, `scope_key=angle_name`. `signal_json`:
`{brier_trend, directional_accuracy, regime_breakdown: {regime_tag:
{n, brier}}, ticker_cluster_breakdown}`. `evidence_count` = count of
`angle_calibration_entries` rows in the trailing window.

**Manageability**: bounded at ~29 rows max (one per registered angle),
independent of watchlist size — deliberately **not** per-ticker despite
touching per-ticker data (see `00-index.md`'s manageability headline).

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/angle_trust.py`.
**Implementation note**: the "trailing-30 mean moves outside the
trailing-90 P10/P90 band" Condition was implemented as two
non-overlapping windows (current = latest 30 entries, reference = up to
90 immediately before them) compared via the same shared PSI machinery
every other analyst in `vinu-reflection` already uses, rather than a
second, bespoke percentile-band function — see that module's own
docstring for the reasoning. `ticker_cluster_breakdown` was not
implemented (scoped down to `regime_breakdown` only); one new reader
method added to `vinu-research`'s `SqliteStrategyStore`
(`distinct_angle_names()`, same pattern as `LlmCallLogStore.distinct_roles()`).

---

## Q. Weight-lineage staleness

**Source stores**: `WeightsStore` (`vinu_initial_analysis/storage/weights.py`:
files at `<data_root>/weights/{symbol}/{angle_name}/{timeframe}/{YYYY}/{YYYYMM}/{bar_ts}.pt`,
referenced by `weights_ref`) · `angle_calibration_entries` filtered to
the 7 deep-learning angles (`arima, dlinear, itransformer, lpatchtst,
lstm, patchtst, tft, tips_regime_aware_transformer`).

**Fetch**: for each `(symbol, angle_name)` pair among the 7 DL angles,
gather the `weights_ref` history (age of each checkpoint) plus every
`angle_calibration_entries` row whose result referenced that
`weights_ref`.

**Condition**: directional-accuracy rate for runs sharing the current
`weights_ref` drops below the trailing P10 of accuracy across all prior
`weights_ref` generations for this `(symbol, angle_name)` — **or** the
current `weights_ref`'s age exceeds 2× the trailing median retrain
interval observed for this angle historically.

**Storage**: `scope_type=ticker`, `scope_key=f"{symbol}:{angle_name}"`.
`signal_json`: `{weights_ref, age_days, accuracy_trend,
retrain_interval_percentile}`. `evidence_count` = # calibration entries
recorded under the current `weights_ref`.

**Manageability**: ≤7 angles × N tickers — linear, further cut hard by
the significance gate (staleness is a slow, rare event per ticker).

**Deferred, 2026-09-19 — not attempted this pass.** `WeightsStore` lives
in `vinu-initial-analysis`, the one service already flagged (twice, in
`02-analyst-interface.md`'s history and the original
mount-vs-ticker-profile design discussion) as too dependency-heavy
(torch/xgboost/chronos-forecasting/timesfm) to mount-and-import the way
`vinu-reflection` currently does for vinu-agent/vinu-research. Building
Q the same way D/L/M/A were built would reintroduce exactly the problem
the shared ticker-profile mechanism (`vinu-infra/TICKER_PROFILE.md`)
exists to avoid — and the ticker-profile file's own
`vinu_initial_analysis` key today only carries `timeframe`/`tier`/
`run_id`/`row_count` per angle, not `weights_ref`/checkpoint age, so it
can't answer Q's Condition either without a producer-side change. Not a
hard blocker like K (no missing data, just a real dependency-cost
tradeoff) — worth a deliberate decision before building, not a default.

**Re-investigated 2026-09-20 (found worse, then reframed and built).**
Asked to think harder about where Q was missed. Traced `weights_ref` all
the way through the real attribution pipeline and found the "dependency
cost" framing was hiding a deeper problem: `weights_ref` is written ONLY
by each DL angle's offline walk-forward `backtest.py` (via
`run_walk_forward`'s `weights_sink`,
`vinu-tools/vinu_tools/compute/backtest/walk_forward.py`). The LIVE
forecast path each angle actually runs on schedule (`compute.py`,
dispatched by `AngleRunner`) never saves or references a checkpoint at
all — confirmed by reading `lstm/compute.py` directly. There is no
"currently-live model checkpoint" concept anywhere in production for
these angles. Also confirmed independently: `angle_calibration_entries`
(vinu-research) has no `weights_ref` or `symbol` column, and
`Artifact.origin_angles` comes from an LLM's free-form self-report
(`angles_used`), never a specific checkpoint. Q's original premise (is
the live checkpoint stale, joined to real trade outcomes) has nothing
real to point at — a dead end, same category as J's original framing.

What IS real: `orchestration_registry.py` maps every DL angle to its
`backtest.py` entry point, invoked on a real (if only quarterly,
`quarters.py`) schedule, writing an immutable `tier2` Parquet record
with real `bar_ts`/`hit`/`weights_ref` columns per walk-forward step —
readable with `pandas`/`pyarrow` alone (confirmed by reading
`AngleStorage`'s own imports directly), no torch/xgboost/chronos/
timesfm needed, since those are only imported by the angle-computation
modules, not the storage layer. Rebuilt around that: `dl_angle_backtest_
health.py` (new file, `vinu-reflection`) reads the latest walk-forward
run per (symbol, angle) via the new `_initial_analysis_parquet.py`
reader (a data-only mount, never an install of `vinu_initial_analysis`
itself — see `docker-compose.yml`'s new `initial-analysis-data` mount),
and computes two honest, self-contained questions instead of Q's
original live-checkpoint one: (1) adjacent-window PSI trend on the `hit`
series, same shape as `angle_trust.py` (A); (2) is the backtest record
itself overdue for its next quarterly recompute (`stored_at` age vs 2x
`VINU_TIER2_PERIOD_MONTHS`). `DL_ANGLES` is the real 7 (`dlinear,
itransformer, lpatchtst, lstm, patchtst, tft,
tips_regime_aware_transformer`) — confirmed by checking `weights_sink`
usage in all 8 angles the design doc's own text lists; ARIMA never
calls it (a classical per-step refit with nothing to checkpoint), which
also resolves that "7 vs 8 names" discrepancy in this file's own
earlier text.

---

## P. Ingest health → forecast quality

**Source stores**: `symbol_catalog` (vinu-stock-price
`vinu_stock_price.db`: `gap_count, has_adj_data, backfill_status`) ·
`backfill_runs` (`rows_rolled, errors JSON`) · `ingest_log` (per-attempt
`ok`/`error`, currently write-only anywhere else in the system) ×
`angle_calibration_entries` for the same symbol/window.

**Fetch**: per symbol, pull trailing `gap_count` / ingest-error rate
from `symbol_catalog` + `ingest_log`, joined against `brier_score` from
`angle_calibration_entries` for runs in the same date window.

**Condition**: this symbol's error-adjusted `brier_score` (windows with
a nonzero gap/error flag) is worse than this same symbol's own
gap-free-period baseline by more than a trailing P10/P90 band — **or**
`gap_count` itself exceeds this symbol's own trailing P90.

**Storage**: **merged with G below** — `scope_type=ticker`,
`scope_key=symbol`. `signal_json`: `{gap_count, error_rate,
brier_delta_vs_clean_periods}`. `evidence_count` = # `ingest_log` rows
in the trailing window.

**Manageability**: ≤N tickers, linear.

**Built 2026-09-19, `vinu-reflection/vinu_reflection/reflection/
ingest_health.py` (merged with G below).** The 2026-09-19 "Blocked"
verdict originally recorded here was a documentation error, found and
corrected the same day while investigating V (02-regime-risk-coverage.md):
it claimed `calibration.py`'s `add_entry()` "leaves
[`CalibrationEntry.timestamp`] at the dataclass default (`""`)" and that
"no real writer anywhere in the codebase ever sets it." Checked directly:
`add_entry()` (`vinu_research/calibration.py`) sets
`timestamp=datetime.now(timezone.utc).isoformat()`, and `git blame` shows
that line has been there since 2026-07-27 — two months before the
"blocked" verdict was written. It is wired to a real production writer:
vinu-live's `feedback_loop.py` calls `POST /trade-plan/{id}/record-
outcome` on every closed position, which calls `record_realized_outcome()`
-> `CalibrationTracker.add_entry()` -> `append_calibration_entry()`, and
`strategy_store.py`'s `append_calibration_entry`/`_row_to_calibration_entry`
persist/read that column verbatim. `calibration_entries.timestamp` is
genuinely populated today — this was never a real data gap.

**Real join used**: not a naive per-entry timestamp match.
`CalibrationEntry.timestamp` is the trade's *close* time, not when the
forecast was made — an ingest gap or provider fallback that degraded a
forecast would have happened near the trade's *entry*, not its close.
Joined on `Artifact.created_at` instead (the real forecast-authoring
moment): each closed position's calibration entries are attributed to
the calendar day its owning artifact was created, and that day (plus a
1-day lag) is checked against `ingest_log`'s bad-day set (P) and
`provider_fallback_log`'s fallback-day set (G) for that same symbol —
real calendar time on both sides, using `ingest_log`/`provider_fallback_
log`'s real Unix timestamps and `Artifact.created_at`'s real ISO
timestamp.

**Scoped down from the Condition above, documented, not silently
dropped**: "`gap_count` itself exceeds this symbol's own trailing P90"
needs a historical *time series* of `gap_count` per symbol; only a
current snapshot lives in `symbol_catalog` (no history table exists for
it anywhere). Only the error-adjusted brier comparison half of P (and
G's fallback-vs-primary equivalent) is implemented; `gap_count` is
still reported in `signal_json` as context. `ingest_log` also needed its
first real read method (`CatalogStore.list_ingest_log`, additive) — it
was write-only everywhere else, exactly as this Condition originally
noted.

---

## G. Data provenance → forecast quality

**Source stores**: `provider_fallback_log` (vinu-stock-price, built
2026-09-15: `symbol, role, winning_provider, skipped_errors JSON,
occurred_at`) × `angle_calibration_entries` for the same symbol/window.

**Fetch**: per symbol, compare `brier_score` for windows served by a
fallback provider (per `provider_fallback_log`) against windows served
by the primary provider.

**Condition**: `brier_score` when served by a fallback provider is worse
than this symbol's own primary-provider baseline by more than the
trailing P10/P90 band.

**Storage**: **merged into P's row** (same `scope_key=symbol`) rather
than a separate finding — P and G answer adjacent questions off
adjacent tables and would otherwise double the per-ticker row count for
no added signal. `signal_json` on P's row gains
`{fallback_brier_delta, fallback_frequency}`. `evidence_count` gains
the # `provider_fallback_log` rows in the window.

**Manageability**: no additional row fan-out beyond P.

**Built 2026-09-19, same module as P above** (`ingest_health.py`,
merged into P's per-ticker row). See P's own note above — the "blocked"
verdict for both was a documentation error, not a real data gap.

---

## S. Fact-sheet vs. LLM-summary divergence

**Source stores**: deterministic fact sheets
(`vinu_initial_analysis/storage/factsheet.py`:
`<data_root>/factsheets/{symbol}/{angle_name}.md`, regenerated via
`generate_factsheet()`) × `ticker_summaries.summary` (the Summary
Agent's LLM prose) for the same `ticker`/`source_run_id`.

**Fetch**: per ticker, extract the numeric claims the deterministic
fact sheet makes and check whether the LLM summary's prose contains a
materially different number for the same claim, or references an
angle the fact sheet shows as `row_count=0` (not actually present).

**Condition**: any numeric divergence beyond a fixed relative tolerance
(domain-bounded — e.g. >5% relative difference on a shared numeric
claim) — this is the one analysis where a fixed tolerance is
appropriate rather than a trailing band, since it's a direct
ground-truth comparison, not a trend. Also flags if the LLM references
an angle the deterministic sheet shows has no real data.

**Storage**: `scope_type=ticker`, `scope_key=symbol`. `signal_json`:
`{divergent_claims: [...], severity}`. `evidence_count` = # numeric
claims compared this cycle.

**Manageability**: ≤N tickers, linear — but cheap per row (a diff, not
a statistical join), so low compute cost regardless of watchlist size.

**Not attempted, 2026-09-19.** Different kind of gap from Q/P/G — this
one needs a real spec, not a missing writer: "extract the numeric claims
the deterministic fact sheet makes and check whether the LLM summary's
prose contains a materially different number for the same claim" is a
genuine text-extraction problem (matching a number in Markdown against
the same number paraphrased in LLM prose) that has no existing parser
anywhere in this codebase to reuse, unlike every other analysis built so
far (D/L/M/A all reused real, already-written query/store code). Writing
one now would mean inventing new, untested numeric-claim-matching logic
under this session's time budget — exactly the kind of thin,
un-vetted implementation this whole design otherwise avoids. Left for a
dedicated pass once there's a real extraction approach to build against,
not a default "skip."
