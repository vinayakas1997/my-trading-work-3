---
name: implementation-status-vinu-initial-analysis
status: all-phases-done
purpose: tracks real code changes made to vinu-initial-analysis against 03-storage-design.md's rules and the confirmed mtime "latest run" bug.
---

# vinu-initial-analysis — Implementation Status

## What's built

- **Required data root**: `config.py` now calls
  `require_data_root("INITIAL_ANALYSIS")`. This var name was already
  correctly named in the real code before this phase — only the
  cwd-fallback default was removed.
- **`_ensure_dotenv_loaded()` was never actually called** — a pre-existing
  gap (the function existed but `load_config()` never invoked it, so a
  `.env` file was silently never read for this component). Fixed:
  `load_config()` now calls it.
- **New `runs_db_path` config field**: `{data_root}/vinu_initial_analysis_runs.db`,
  replacing the old inline `config.data_root / "runs.db"` used at every
  construction site.
- **`RunLog` migrated onto `vinu_infra.sqlite.SQLiteBackend`**
  (`storage/meta.py`) — was hand-rolling its own `sqlite3.connect` before
  (the one confirmed gap where this component didn't reuse
  `SQLiteBackend`, unlike vinu-news/vinu-stock-price). All existing
  methods (`record_run`, `get_runs`, `get_latest_run`, `has_existing_run`)
  kept their exact signatures, now backed by the shared base class.
  `get_latest_run` also gained a `completed_only` filter (default `True`)
  — it previously didn't filter by status at all.
- **The confirmed mtime-based "latest run" bug is fixed**
  (`storage/parquet.py`): `AngleStorage.read()`/`read_latest()` now
  resolve the current run through `RunLog.get_latest_run()` (SQL,
  `ORDER BY started_at DESC`, `status='completed'`) when a `run_log` is
  wired into the `AngleStorage` instance, matching
  `../03-storage-design.md` section 7 exactly. Wired in at the 3 places
  that construct both together: `api.py` (serves `/analysis/*`),
  `cli.py`'s `run`/`serve` commands. The mtime scan is kept **only** as
  a fallback for the handful of call sites that build a throwaway
  `AngleStorage` without a `run_log` for internal upstream-angle reads
  (`trend_lifecycle`/`trend_session_structure`'s own compute modules) —
  documented in the code as a known, intentional gap, not a design
  choice.
- `.env` created at `vinu-initial-analysis/.env` (gitignored) with
  `VINU_INITIAL_ANALYSIS_DATA_ROOT=./data`.
- Test fixtures fixed: `tests/test_api.py` and `tests/test_pnl_attribution.py`
  construct `VinuInitialAnalysisConfig(...)` directly with an explicit
  `data_root`, but didn't also pass `runs_db_path` — its default factory
  still called `require_data_root()` and failed even though `data_root`
  was already given explicitly. Both fixed to pass `runs_db_path`
  explicitly too.

## Tested

```
90 passed, 11 failed, 2 skipped
```

The 11 failures (`test_shock_clustering.py`, `test_shock_personality.py`
— all `KeyError: 'bar_ts'`) are **confirmed pre-existing** — reproduced
identically with this phase's changes fully reverted via `git stash`
(11 failed / 21 passed on just those files either way). Unrelated to
this phase; not fixed here, out of scope.

## Phase 3: storage path shape — done

`AngleStorage`/`RunLog` now implement the full `03-storage-design.md`
section 6/7 shape:
- Single-ticker: `{root}/analysis/{symbol}/{angle}/{granularity}/{tier}/{run_id}.parquet`
- Multi-ticker (new `tickers=` param on `write`/`read`/`read_latest`):
  `{root}/analysis/_multi/{sha256-12char}/{angle}/{granularity}/{tier}/{run_id}.parquet`,
  hash over sorted-uppercased-joined tickers.
- `granularity`/`tier` added as columns to `RunLog`'s `runs` table and
  threaded through `record_run`/`get_latest_run`/`has_existing_run`.
- **Tier-aware pruning fixed**: `_cleanup()` now no-ops entirely for
  `tier2` — a tier2 write is never a deletion candidate, which is what
  actually enforces the immutability principle in code rather than just
  stating it.
- Defaults (`granularity="1D"`, `tier="tier2"`) keep every existing call
  site (`runner.py`, `api.py`, `cli.py`, the 13 angles) working
  unchanged — none of today's angles have a real granularity concept
  yet, so none were forced to invent one. New methods that do care about
  granularity (Phase 5) pass it explicitly.
- Multi-ticker reads always use the mtime-scan fallback rather than
  `RunLog` — `RunLog`'s schema keys by a single `symbol` column with no
  ticker-hash key yet, and no multi-ticker angle exists to need it yet.
- Tested: `tests/test_parquet.py` extended with a `TestAngleStoragePathShape`
  class (nested path, granularity isolation, multi-ticker routing/hashing,
  `list_symbols()` excluding `_multi`) plus a `test_tier2_is_never_pruned`
  regression test. Full suite: **97 passed** at that point (baseline 90 + 7 new).

## Phase 4: angle reconciliation — done

- **`garch` extracted**: new `angles/garch/`, reusing the exact same
  `vinu_tools.compute.risk.volatility.garch_volatility` call that
  `shock_personality` already makes internally — verified identical fits
  via a cross-check test (`test_garch.py::test_matches_shock_personality_vol_persistence_fit`)
  rather than reimplementing GARCH.
- **`ml_model_pipeline` and `news_first_analysis` marked deprecated, not
  deleted**: both got a clear docstring in their `compute.py` explaining
  what supersedes them (the TSFM family for the former, vinu-news's
  `analysis/methods/` for the latter) and a `[DEPRECATED — ...]` prefix
  on their `catalog/angles.yaml` purpose text. **Deliberately not
  physically removed** — deleting a working, tested feature is a more
  consequential and harder-to-reverse action than the rest of this pass,
  and the reconciliation doc's "replace, don't run both" language reads
  as a recommendation for what to build toward, not an explicit mandate
  to delete code immediately. Both angles still run and are still
  tested; actual removal is left as a deliberate follow-up decision.

## Phase 5 Section 2a: classical stats — done

- `angles/arima/` — ARIMA(p,d,q) on `bars["close"]` via small AIC grid
  search (p∈{0,1,2}, d∈{0,1}, q∈{0,1,2}); one-step forecast + 95% CI +
  fitted order/AIC. `insufficient_data` below 30 observations.
- `angles/kalman_filters/` — `statsmodels.tsa.statespace.structural
  .UnobservedComponents` (local linear trend), a genuine two-state
  (level, trend) Kalman filter/smoother; returns filtered + smoothed
  estimates with state-covariance-derived std devs — a present-state
  estimate, not a forecast, matching the spec's framing.
- `angles/exponential_smoothing/` — Holt's linear trend
  (`statsmodels.tsa.holtwinters.ExponentialSmoothing`, trend="add", no
  seasonal component — daily equity bars have no reliable fixed
  seasonal period, and the spec calls seasonality optional).
- No new pip deps — `statsmodels` was already a dependency.
- 15 new tests, all passing (confidence intervals bracket point
  forecasts, params in valid ranges, insufficient-data degradation).

## Phase 5 Section 2b: trained-from-scratch neural family — done

- `angles/{dlinear,lstm,patchtst,itransformer,tft,lpatchtst,tips_regime_aware_transformer}/`
  — real, small PyTorch models trained in-process on `bars["close"]`
  (CPU-only, a handful of epochs, fast enough for synchronous per-request
  computation — not a production training pipeline).
- DLinear: trend/seasonal decomposition (AvgPool) + two linear heads.
  LSTM: single-layer, 16-hidden recurrent net. PatchTST: shared
  `PatchEncoderBranch` (patch-embed + `TransformerEncoder`) factored into
  `patchtst/_patch_transformer.py`.
- **Correction to the plan's own naming assumption**: the "L" in
  LPatchTST is **LSTM**, not "lightweight" — confirmed directly from
  `23-lpatchtst.md`'s own title/explanation. `lpatchtst/compute.py`
  fuses the same `PatchEncoderBranch` with an LSTM branch (concatenated
  representations, one linear head) rather than being a smaller PatchTST
  config.
- iTransformer: `compute()` only receives one symbol's `bars`, so true
  cross-*ticker* attention isn't available without a live `price_client`
  — OHLCV **channels** (open/high/low/close/volume) substitute as the
  variate-tokens instead, documented as a deviation in the code.
- TFT: gated variable-selection network + LSTM + self-attention +
  quantile heads reparameterized as median ± softplus(deltas) to
  guarantee non-crossing P10≤P50≤P90 — a real quantile-crossing bug was
  caught and fixed during the agent's own testing, not left in.
- TIPS regime-aware transformer: lag-1 return autocorrelation over a
  trailing window classifies momentum vs. mean-reversion; the pooled
  transformer output routes through one of two regime-specific linear
  heads via `torch.where` (gradient only flows to the responsible head
  per sample) — a structural regime adaptation, not just a concatenated
  feature.
- Not fully satisfied: iTransformer's true multi-ticker joint input, and
  TFT's known-future-inputs/static-covariates (no such data available
  from `bars`/`news`) — both documented in-code, not silently dropped.
- New pip dep: `torch>=2.2` (CPU wheel), added to `pyproject.toml`.
- 30 new tests, all passing. Independently verified: **160 passed**
  after this batch (130 prior + 30 new), same 11 pre-existing failures,
  zero new regressions from this batch specifically (one new failure at
  this checkpoint, `test_timegpt.py`, belongs to the still-in-progress
  Section 2c batch below, not this one).

## Phase 5 Section 2c: foundation models + fusion architectures — done

12 methods, each honestly labeled by actual backend (`model_backend`
field in the output — every angle's output says which one ran, never
silently pretending):

| Method | Backend | Why |
|---|---|---|
| `chronos` | **pretrained** | real `chronos-forecasting` package, `amazon/chronos-t5-tiny` loaded live from HF Hub |
| `timesfm` | **pretrained** | real `timesfm[torch]` package, `google/timesfm-2.5-200m-pytorch` (200M params) loaded live |
| `cross_attention_gcn_news_price_fusion` | `trained_in_process` | real small PyTorch bidirectional cross-attention over price + bag-of-words news features; the GCN's cross-stock layer is structurally degenerate to a single-node self-loop since `compute()` is per-symbol, honestly flagged via `gcn_note` |
| `kronos` | fallback_proxy | no PyPI package, only a non-packaged GitHub repo |
| `timegpt` | fallback_proxy | confirmed paid hosted API (Nixtla), no API key available |
| `moirai` | fallback_proxy | `uni2ts` would downgrade the shared env's torch build (risk to concurrent sibling work), and can't exercise any-variate multi-ticker attention from this per-symbol interface anyway |
| `moment` | fallback_proxy | `pip install momentfm` genuinely fails in this Python 3.12 environment (build error) |
| `timer_timerxl` | fallback_proxy | not on PyPI, only a non-packaged research repo |
| `lag_llama` | fallback_proxy | not on PyPI, manual-clone + separate checkpoint only |
| `patchformer` | fallback_proxy | not on PyPI; spec itself couldn't confirm the real architecture |
| `fincast_foundation_model` | fallback_proxy | spec flags availability as unconfirmed, no package given |
| `finmamba_graph_state_space` | fallback_proxy | spec discloses no param count/no package |

New pip deps: `chronos-forecasting>=1.4`, `timesfm[torch]>=2.0`. HF model
cache (~1.4GB) confirmed outside the repo tree (`~/.cache/huggingface`),
nothing leaked into git. 41 new tests, all passing. Independently
verified after this batch: **187 passed**, same 11 pre-existing failures,
zero new regressions.

**Overall Phase 5 Section 2 total**: 22 methods across all 3 sub-batches
(3 classical + 7 trained-from-scratch + 12 foundation/fusion), zero
faked results — every non-pretrained method is honestly labeled as such
in its own output.

## Registry consolidation

All 22 new methods (plus `garch`, plus a pre-existing gap found along
the way — `peer_relative_strength` was never in `catalog/angles.yaml`
at all, confirmed via `git show HEAD:...` on the original file — added
too) registered in `catalog/angles.yaml`, generated programmatically
from each angle's own `spec.yaml` to avoid transcription errors.
**35 total angles**, no duplicates (verified). This consolidation was
deliberately withheld from every Phase 5 background agent (each was
told not to touch `catalog/angles.yaml`) specifically to avoid
concurrent-write conflicts on a shared file — done once, by hand, after
all agents landed.

## Phase 6c: API redesign — done

New `vinu_initial_analysis/server/routes_v1.py`, mounted at
`/v1/stage1/vinu-initial-analysis/*` alongside the existing `/analysis/*`
routes (unchanged, still there).

- `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/{granularity}/{time-range}/{method}`
  — always resolves the **tier2** (scheduled/official) result. `404` if
  none exists — `fetch` never auto-triggers, per `02-api-design.md`.
- `POST /v1/stage1/vinu-initial-analysis/trigger/{ticker}/{granularity}/{time-range}/{method}`
  — `202`, assigns a `run_id`, kicks off a real single-angle
  `AngleRunner` run in a background thread, writing to **tier3**
  (triggered/ad-hoc).
- `GET .../fetch/{ticker}/{granularity}/{time-range}/{method}/{run_id}`
  — polls that specific trigger: `202`/`computing` while running, then
  resolves the tier3 result once done, `404` for an unknown run_id.

**Real plumbing change needed and made**: the existing runner/API/service
chain had no way to pre-assign a `run_id` or choose a `tier` — both were
always internally generated/defaulted. Threaded `run_id` and `tier`
as optional params through `AngleRunner.run()`/`_run_angle()` →
`CorrelationAPI.compute_and_store()` → `InitialAnalysisService.run_analysis()`,
so the ID returned immediately at trigger-time is the exact same one
that ends up in `RunLog`/storage, and a triggered run actually lands in
tier3 as its response claims (see "Two real bugs" below).

**Known, honestly-documented limitation**: none of the 35 angles thread
a real `{granularity}` through to `AngleStorage` yet — every write still
lands under the default `1D` bucket regardless of what `time_format` an
angle computed at internally. `fetch`/`trigger` validate and pass the
segment through correctly, but requesting anything other than the
`1day`-equivalent bucket finds nothing today. This is a scope boundary
(Phase 3 built the storage *shape*; retrofitting every angle's write
path to use real granularity is separate follow-up work), not a bug in
this route.

**Two real bugs caught and fixed while building this** (both would have
shipped broken without independent verification catching them):
1. `trigger`'s response claimed `tier="tier3"`, but `tier` was never
   actually threaded through `InitialAnalysisService.run_analysis()` —
   the write silently defaulted to `tier2` regardless of what the
   response said. Fixed by threading `tier` through the same chain as
   `run_id` above.
2. `fetch_by_run`, once a triggered run completed, delegated to the
   plain `fetch()` — which is hardcoded to look in `tier2`. Since
   `trigger` always writes `tier3`, polling would find nothing and
   report `not_found` even for a successfully completed run. Fixed by
   giving `fetch_by_run` its own tier3-scoped lookup instead of
   delegating.

Tested: `tests/test_api_v1.py`, 7 tests (422s for bad
granularity/unknown method, 404 for no data, granularity isolation is a
real filter not decorative, full trigger→poll→resolves-in-tier3 flow,
confirming a plain tier2 fetch does *not* see a tier3-triggered result).
Full suite after this: **194 passed**, same 11 pre-existing failures,
zero regressions.

## Not yet done

- **`ParquetStore` adoption** — still bespoke Parquet code, not routed
  through `vinu_infra.parquet.ParquetStore`. Deliberate, not an oversight
  — same reasoning as vinu-stock-price's decision (see
  `03-vinu-stock-price.md`): the bespoke code already does what's needed
  correctly.
- **Real per-angle granularity** — see Phase 6c's documented limitation
  above; every angle still writes under the default `1D` bucket.
- **`ml_model_pipeline`/`news_first_analysis` physical removal** — marked
  deprecated, intentionally not deleted (see Phase 4 above); a follow-up
  decision if you want them actually removed.

## Post-Phase-6 decision: 4 permanent-fallback angles physically removed (2026-08-06)

Of the 12 `fallback_proxy` angles from Phase 5 Section 2c, 4 had **no path
to real weights at all** (no checkpoint exists or ever will) rather than
being blocked by an environment/dependency conflict: `timegpt` (paid
Nixtla API, no self-hostable checkpoint), `patchformer` (no PyPI package,
spec couldn't confirm the real architecture), `fincast_foundation_model`
(no package/checkpoint, only paper links), `finmamba_graph_state_space`
(no param count disclosed, no package or repo).

Decision: a permanent fake is more confusing to keep in the codebase than
useful — unlike `moirai`/`moment`/`lag_llama` (weights already downloaded
into `data/models/`, blocked only by dependency conflicts — a real,
finishable follow-up), these 4 would never graduate past their proxy.
Removed:
- `angles/{timegpt,patchformer,fincast_foundation_model,finmamba_graph_state_space}/`
  (each `compute.py` + `spec.yaml`) deleted entirely.
- `tests/test_{timegpt,patchformer,fincast_foundation_model,finmamba_graph_state_space}.py`
  deleted.
- `catalog/angles.yaml` entries removed (angle discovery is filesystem-driven
  off `angles/`, so no registry code needed updating) — **31 angles remain**
  (down from 35).
- `pyproject.toml` description string corrected to match (was already
  stale at "25" pre-removal; now "31").
- `vinu-infra/models.py`'s doc comment updated to reflect the angles are
  gone, not just absent from the download registry.

Net effect: the 32-method plan now has **28 implemented methods** (9
news-only + 19 price-dependent in vinu-initial-analysis, down from 23 —
3 classical + 7 trained-from-scratch + 9 foundation/fusion, of which 2 are
genuinely `pretrained` and the remaining 7 stay honest `fallback_proxy`/
`trained_in_process`) plus 3 fallback-proxy angles (`moirai`/`moment`/
`lag_llama`) with a real, documented path to becoming pretrained later.
