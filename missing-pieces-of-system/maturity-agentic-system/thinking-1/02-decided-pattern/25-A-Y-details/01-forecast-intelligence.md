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
