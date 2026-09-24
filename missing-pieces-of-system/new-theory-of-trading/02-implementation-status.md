# Implementation status

Tracks what's actually been built against the decisions in
`01-planning.md`, updated as implementation proceeds. "Tested" means a
real test was run and observed passing in this environment, not just
written.

## Phase 1 -- `vinu-infra` model policy + manifest (Decisions 4, 5, 6, 7)

**Status: implemented and tested.**

### What was built

1. **`vinu-infra/model_policy.py`** (new file) -- Decision 4.
   - `models_enabled()` -- reads `VINU_MODELS_ENABLED` (boot-only module
     constant, default true), matching the existing precedent in
     `vinu-live/vinu_live/trade_plan/orchestrator.py` that feature kill
     switches stay `.env`-only, not live-editable.
   - `get_model_checkpoint(angle_name, default)` -- per-angle string
     override (`VINU_<ANGLE>_CHECKPOINT`), extending
     `vinu-initial-analysis`'s existing `get_angle_setting()` convention
     (which is int-only) to strings.
   - `policy_version()` -- deterministic 12-char hash of
     (`MODELS_ENABLED` + every `VINU_*_CHECKPOINT` override actually
     set), the version stamp Decision 7 requires.

2. **`vinu-infra/system_manifest.py`** (new file) -- Decision 6.
   - `resolve_active_angles(angles)` -- filters a discovered angle list
     down to what will actually run: permanently-disabled angles always
     excluded, `category: model` angles additionally excluded when
     `models_enabled()` is false.
   - `build_manifest(angles)` -- the full startup report: angle
     inventory by category, current policy + version, active angle
     count, recording time-format in effect (15-minute per Decision 2,
     with angles that don't declare support for it flagged), and the
     evidence-table column count (fixed schema columns + one per active
     angle-based indicator).
   - `PERMANENTLY_DISABLED_ANGLES = {"moirai", "moment", "lag_llama"}`
     (Decision 5) -- enforced by identity, not by trusting each angle's
     own `category` tag, so a mis-tagged spec.yaml can't accidentally
     re-enable one.

3. **`category` field added to all 28 angles' `spec.yaml`** -- checked
   against each angle's real implementation (torch/pretrained-weights
   import, or a documented `fallback_proxy`), not guessed from the name:
   - `model` (11): chronos, dlinear, itransformer, kronos, lpatchtst,
     lstm, patchtst, tft, timer_timerxl, timesfm,
     tips_regime_aware_transformer
   - `disabled` (3, with `disabled_reason`): moirai, moment, lag_llama
   - `news` (1): news_price_causality
   - `raw_data` (13): everything else
   - All 28 files validated as parseable YAML with `category` present
     after the edit.

4. **`chronos/compute.py` wired to the new policy** -- `CHECKPOINT` and
   `_MODEL_REGISTRY_NAME` are no longer hardcoded; `_MODEL_REGISTRY_NAME`
   resolves via `get_model_checkpoint(ANGLE_NAME, "chronos-t5-large")`
   and `CHECKPOINT` resolves that name against `vinu-infra/models.py`'s
   existing `MODELS` registry dict (so an override selects an
   already-registered checkpoint, e.g. `chronos-t5-tiny`, not an
   arbitrary unvetted HF repo id). Falls back to the decided default if
   the override names an unknown registry entry.

5. **`AngleRunner.run()` (`vinu-initial-analysis/runner.py`) enforces the
   policy** -- `resolve_active_angles()` is applied *before* the
   caller's own `angle_names` filter, so a caller can't force-run a
   permanently-disabled or (when `MODELS=false`) a model-category angle
   by naming it explicitly.

6. **`RunLog` (`vinu-initial-analysis/storage/meta.py`) stamps
   `policy_version` per run** -- Decision 7.
   - Real schema migration (`SCHEMA_VERSION = 2`,
     `ALTER TABLE runs ADD COLUMN policy_version TEXT`), not a
     clean-slate rewrite -- the real production db
     (`data/initial-analysis/vinu_initial_analysis_runs.db`) already had
     1,316 rows at the time this was built. Migration tested against a
     copy of that real file (see Tests below); auto-applies on next
     connection in production (SQLiteBackend runs pending migrations on
     every fresh connection).
   - Both `record_run()` call sites in `runner.py` (the failure-path
     call and the per-time-format success-path call) now pass
     `policy_version=policy_version()`.

### Tests (all run and observed passing in this environment)

- `vinu-infra/tests/test_model_policy.py` -- 12 tests: default/override
  behavior for both knobs, several falsy-string spellings for
  `VINU_MODELS_ENABLED`, `policy_version()` stability under an unchanged
  env and its change when either knob changes.
- `vinu-infra/tests/test_system_manifest.py` -- 7 tests: permanently-
  disabled exclusion wins over a mis-tagged `category` (fixture
  deliberately tags "moment" as `raw_data` to prove identity-based
  exclusion, not tag-based), models-off drops model-category angles but
  leaves raw_data/news untouched, angle-inventory counts, evidence-table
  column count tracks active angle count exactly, missing-time-format
  flagging, and the manifest's column count + `policy_version` both
  changing when `MODELS_ENABLED` flips.
- `vinu-initial-analysis/tests/test_runner_model_policy.py` -- 3 tests,
  using the same real-temporary-angle-under-`ANGLES_DIR` fixture pattern
  as the existing `test_runner_time_format.py`: a fake `category: model`
  angle runs when models are enabled, is skipped when disabled even when
  named explicitly in `angle_names`, and the real (already-discovered)
  `moirai` angle never runs no matter what its own tag says.
- `vinu-initial-analysis/tests/test_chronos.py` -- 2 new tests appended:
  checkpoint override resolves via the shared `vinu-infra/models.py`
  registry (`VINU_CHRONOS_CHECKPOINT=chronos-t5-tiny` ->
  `CHECKPOINT == "amazon/chronos-t5-tiny"`), and an override naming an
  unknown registry entry falls back to the decided default rather than
  producing an unusable checkpoint string.
- `RunLog` migration -- verified directly (not via pytest) against a
  **copy of the real production database**
  (`data/initial-analysis/vinu_initial_analysis_runs.db`, 1,316 real
  rows at migration time): migration applied cleanly, `PRAGMA
  user_version` reached 2, all 1,316 existing rows preserved with
  `policy_version` NULL (honest -- no policy was tracked for runs
  before this decision existed), and a newly inserted row correctly
  carries a real `policy_version` value. Copy discarded after
  verification; production file itself untouched by this check (it will
  migrate itself automatically the next time any process opens it, per
  `SQLiteBackend._init_schema`'s existing behavior).

### Regression check

Full `vinu-infra` test suite: **286 passed**, no regressions.

`vinu-initial-analysis` test suite (excluding files that fail to even
*import* in this sandbox due to `torch` not being installed here, and
excluding the one pre-existing network-dependent chronos test):
**374 passed**, no regressions. Every failure observed while running the
broader suite was independently reproduced against the unmodified
codebase via `git stash` -- confirmed pre-existing (no `torch` package,
no Hugging Face Hub network access in this sandbox), not caused by this
work:
- `ModuleNotFoundError: No module named 'torch'` -- 16 test-collection
  errors + several test failures across dlinear/itransformer/lstm/tft/
  tips_regime_aware_transformer/kronos_backtest/test_factsheet (which
  imports the orchestration registry, which imports dlinear's backtest,
  which imports torch transitively) and test_admin/test_baseline/etc.
- Real-network-required pretrained-weights tests failing closed to
  `fallback_proxy` -- chronos, kronos, timer_timerxl, timesfm's own
  "pretrained backend actually loads in this environment" tests. Same
  failure exists on unmodified `main`.

### Known limitations / left for later

- The manifest's evidence-table column count only counts angle-based
  supporting indicators (Section A of
  `all-possible-supporting-indicators.md`). The non-angle indicators
  (Sections B-G: technical, volume, volatility, microstructure, context,
  meta) aren't angle-discovered and aren't counted yet -- noted directly
  in `build_manifest()`'s own output (`evidence_table.note`).
- `get_model_checkpoint()` overrides are validated against
  `vinu-infra/models.py`'s registry only for `chronos` so far -- the
  other 3 real-checkpoint model-category angles (`timesfm`,
  `timer_timerxl`, `kronos`) still have hardcoded checkpoints. **Update:**
  checked all 11 model-category angles' actual code directly (not
  assumed) -- only these 4 load a pretrained checkpoint at all; the
  other 7 (dlinear, itransformer, lstm, patchtst, tft, lpatchtst,
  tips_regime_aware_transformer) train their own small architecture
  fresh on every call, so "wire the checkpoint override" doesn't apply
  to them at all, not just "not done yet." See
  `vinu-infra/angles_models_config.py` (new file, tested) for the
  per-angle breakdown with this finding recorded directly in code
  comments, ready for whoever does the remaining 3 angles' wiring.
- No HTTP endpoint exposes `build_manifest()` yet. **Update:** this is
  now tracked as its own high-priority planning file --
  `04-pending-manifest-http-endpoint.md` -- since it turned out to have
  real open questions (which service owns the route, auth, response
  shape stability) worth settling before just bolting on a route.
- **New, high-priority, not yet started:** exposing signal-evidence via
  a `vinu-agent` tool call (an LLM-callable `BaseTool`, not just the raw
  HTTP routes) -- tracked in
  `05-pending-signal-evidence-tool-call.md`, including the real design
  question of whether it should be read-only (recommended) or allow an
  LLM to write trigger rows directly (which would reopen the
  look-ahead-bias risk Decision 10 was built to avoid).

## Phase 2 -- recording layer in `vinu-research` (Decisions 1, 2, 3, 7, 8)

**Status: storage + HTTP surface implemented and tested. The live
must-condition detector (the code that would actually call this from
`vinu-live`) is NOT built -- see Known limitations below.**

### What was built

1. **`vinu-research/vinu_research/storage/signal_evidence_store.py`**
   (new file) -- `SignalEvidenceStore`, built on `vinu_infra.sqlite.
   SQLiteBackend` (the same shared backend `vinu-initial-analysis`'s
   `RunLog` uses; `vinu-research`'s own `SqliteStrategyStore` predates
   this shared class and hand-rolls its own connection handling, so this
   new store intentionally uses the newer, more robust shared one rather
   than copying the older local pattern).
   - Two tables: `signal_triggers` (one row per must-condition firing;
     `trigger_id`, `symbol`, `trigger_time`, `must_condition` (JSON list),
     `granularity`, `policy_version`, plus the three outcome-path columns
     from Decision 1 -- `max_favorable_excursion`,
     `max_adverse_excursion`, `return_at_horizon` -- all nullable until
     `record_outcome()` fills them in later) and
     `signal_evidence_indicators` (one row per `(trigger_id,
     indicator_name)` pair, `indicator_data` a JSON blob holding that
     indicator's own natural shape).
   - This is the concrete, real-schema realization of Decision 3's "one
     JSON column per indicator": SQLite has no dynamic columns, so a
     normalized child table keyed by `indicator_name` gives the identical
     property (heterogeneous shapes, zero schema change when an
     indicator's fields change) without an `ALTER TABLE` per indicator --
     documented directly in the module's own docstring so the mapping
     from decision to schema is explicit, not implicit.
   - `record_trigger()` / `record_outcome()` (the two-phase write Decision
     1 requires, since the outcome path can't be known until the horizon
     elapses) / `get_trigger()` (full row + indicators, JSON parsed back
     to native shape) / `list_triggers()` (metadata-only, for browsing) /
     `get_unresolved_triggers()` (the query whatever future outcome-filling
     job would poll -- that job itself isn't built, see Limitations).

2. **`ResearchService`** (`vinu-research/vinu_research/service.py`) --
   gained a `signal_evidence_store` property/constructor param, own db
   file (`signal_evidence.db`, separate from `strategy_store.db` since
   this table is expected to grow much faster -- one row per trigger
   event, not per artifact), closed on `service.close()` the same
   ownership-flag pattern `strategy_store` already uses.

3. **`vinu-research/vinu_research/server/routes_signal_evidence.py`**
   (new file) + wired into `app.py` -- four endpoints:
   - `POST /research/signal-evidence/trigger` -- records a trigger + its
     indicator snapshot; 409 if `trigger_id` already exists (never
     silently overwrites a trigger row -- only `record_outcome` is
     allowed to update an existing row, and only its own three outcome
     fields).
   - `POST /research/signal-evidence/{trigger_id}/outcome` -- fills in
     the outcome path; 404 if the trigger doesn't exist.
   - `GET /research/signal-evidence/{trigger_id}` -- full row + parsed
     indicators.
   - `GET /research/signal-evidence?symbol=...` -- listing, metadata only.
   - Mirrors the exact same "vinu-live detects a real event, POSTs it to
     vinu-research" pattern `routes_trade_plan.py`'s existing
     `.../record-outcome` calibration route already uses -- Decision 8's
     reasoning that this needed no new architecture, just applying an
     already-proven pattern to a new table.

### Tests (all run and observed passing)

- `vinu-research/tests/test_signal_evidence_store.py` -- 10 tests:
  round-trip preserves each indicator's own heterogeneous shape
  (flat dict, nested-list dict, bare scalar) with no flattening; multiple
  must-conditions stored as a list; outcome fields NULL until recorded;
  unknown trigger_id returns None; outcome recording is safe to call
  twice (overwrites, matching Decision 1's "horizon can be revisited"
  design); symbol-filtered/ordered listing excludes indicators;
  unresolved-triggers query respects the caller-supplied cutoff in both
  directions.
- `vinu-research/tests/test_routes_signal_evidence.py` -- 6 tests over a
  real `TestClient`: record-then-read round trip through the full HTTP
  stack, duplicate `trigger_id` rejected with 409, unknown trigger_id
  returns 404 on both read and outcome-record, outcome round-trips
  correctly, symbol-filtered listing.
- Full `vinu-research` regression suite: **992 passed** (986 baseline +
  6 new route tests via the top-level count; the store's own 10 tests
  are additionally counted in this total), 1 pre-existing skip, no
  regressions.

### Known limitations / left for later

- **The actual must-condition trigger detector doesn't exist.** This
  phase built the storage + HTTP surface that a live detector would call
  -- it did not build the detector itself. That requires settling the
  still-open question from `00-explanation.md`'s "Open questions"
  section (where the must-condition / supporting-indicator declaration
  actually lives -- `vinu-strategy` vs. a separate research-layer config)
  before `vinu-live` has anything concrete to evaluate each cycle. Not
  attempted in this pass; scoping it prematurely would have meant
  guessing at an unsettled design decision.
- **No outcome-filling job exists either.** `get_unresolved_triggers()`
  is the query such a job would poll, but nothing calls it on a
  schedule yet -- outcomes must be recorded manually via the HTTP route
  for now.
- **Recording granularity (Decision 2's 15-minute bars) isn't enforced
  by this module.** `SignalEvidenceStore.record_trigger()` accepts
  whatever `granularity` string a caller passes (default `"15min"`) --
  it's stored, not validated. Enforcement belongs with whatever builds
  the trigger detector, which is the thing that actually knows what
  timeframe it's evaluating on.

## Phase 2 extension -- signal-evidence as angle #29, plus per-ticker coverage (Decisions 9, 10, 11)

**Status: implemented and tested. This closes the gap flagged above for
the historical-backfill path specifically** (the still-open item is now
only a LIVE-execution detector inside `vinu-live`, not "no detector
exists at all").

### What was built

1. **`RunLog` gained a real `models_enabled INTEGER` column**
   (`SCHEMA_VERSION = 3`, a real migration, not a clean-slate rewrite --
   verified against a copy of the real production db again, same as the
   `policy_version` migration before it). Set from
   `vinu_infra.model_policy.models_enabled()` at both existing
   `record_run()` call sites in `runner.py`. Exists because
   `policy_version` alone is a one-way hash (deliberately, per
   `model_policy.py`'s own docstring) -- nothing could read "was this
   models-on or models-off" back out of it directly.

2. **`vinu-initial-analysis/vinu_initial_analysis/storage/
   ticker_coverage.py`** (new file) -- `build_ticker_coverage(run_log,
   symbol, all_angles)`, a pure read-side pivot of `RunLog`'s existing
   rows into the wide, one-row-per-ticker shape: covered date range
   (min/max across all the ticker's `analysis_from`/`until`),
   `models_enabled` (the single most recent run's flag, not a blended
   aggregate -- documented as a deliberate choice, since a ticker can
   have angles at genuinely different ages under different policies),
   and per-angle status. Exposed via `GET /analysis/coverage/{ticker}` in
   `routes_read.py`. Deliberately NOT a new table -- would have created a
   second copy of facts `RunLog` already owns, risking drift between the
   two.

   **Revised same day per Decision 11**: a per-angle column is now one
   of three things, not bare present-or-absent -- the angle's real
   status (has run), `"pending"` (required under current model policy,
   hasn't run yet -- a real gap), or `"not_required"` (excluded by
   current policy, e.g. a `category: model` angle while `MODELS=false`,
   or a Decision-5 permanently-disabled angle -- its absence is correct,
   not a gap). An `overall_status` (`"pending"`/`"completed"`) is derived
   the same way, requiring positive evidence (something has actually
   run) before ever reporting `"completed"`. `build_ticker_coverage` now
   takes the full angle roster (name + spec/category) and calls
   `vinu_infra.system_manifest.resolve_active_angles` -- the exact same
   function Phase 1's `AngleRunner.run()` policy filter already uses --
   rather than re-deriving the required/not-required split a second way.
   Real recorded data always wins over the `not_required` label (an
   angle that ran before models were later turned off keeps its real
   status, never gets masked).

3. **`vinu-initial-analysis/vinu_initial_analysis/angles/signal_evidence/`**
   (new angle, `category: raw_data`) -- the historical-backfill detector
   this design needed. For a given symbol's bars over whatever
   `[from_ts, to_ts]` window the run was asked to cover:
   - Finds every historical SMA(5)-crosses-above-SMA(50) event via a
     from-scratch Wilder-style crossing check (no lookahead: `above`/
     `prev_above` computed strictly causally).
   - For each crossing with a complete forward horizon available
     (`FORWARD_HORIZON_BARS`, default 20 bars), computes point-in-time
     ADX(14), RSI(14) (Wilder smoothing, hand-rolled -- no external TA
     package), and volume-vs-20-bar-average -- all computed strictly
     from bars up to and including the trigger bar, never from another
     angle's stored "latest" result (see the look-ahead-bias reasoning
     in Decision 10 and the module's own docstring).
   - Computes the outcome path (max favorable/adverse excursion,
     return-at-horizon) from the bars already available forward of the
     trigger -- valid specifically because backtesting already has
     those "future" bars in hand.
   - POSTs both to `vinu-research`'s Phase 2 HTTP routes
     (`/research/signal-evidence/trigger` then `.../outcome`),
     idempotently: a 409 (already recorded, from a re-run over an
     overlapping window) is counted as `triggers_already_recorded`, not
     an error; a genuine HTTP failure is counted separately
     (`triggers_record_errors`) and does not stop the rest of the
     angle's crossings from being attempted.
   - A crossing too close to the end of the given window (not enough
     bars yet for the forward horizon) is counted as
     `triggers_skipped_incomplete_horizon`, not a failure -- a later run
     with a `to_ts` further forward will pick it up naturally.

### Tests (all run and observed passing)

- `vinu-initial-analysis/tests/test_ticker_coverage.py` -- 8 tests
  (rewritten for Decision 11's three-valued columns): a new ticker
  reports every required angle `"pending"` and the permanently-disabled
  one `"not_required"` regardless of its own tag; `VINU_MODELS_ENABLED=
  false` flips model-category angles to `"not_required"` while leaving
  `raw_data` angles `"pending"`; a real recorded run shows its real
  status; **real data wins over the `not_required` label** -- an angle
  that ran before models were later turned off keeps its real
  `"completed"` status rather than being masked; `overall_status`
  becomes `"completed"` only once every currently-required angle has
  run; `models_enabled` reflects the most recent run specifically, not
  an aggregate; an angle name outside the current roster (simulating one
  removed from disk) is real `RunLog` data but correctly not added as an
  extra column; different tickers stay isolated from each other.
- `vinu-initial-analysis/tests/test_ticker_coverage_route.py` -- 3 tests
  over a real `TestClient`: empty coverage reports `"pending"`
  everywhere (not the old bare-null shape), ticker-case normalization,
  and a real run recorded through `service.run_log` reflected correctly
  through the HTTP route (proving the route reads the same object the
  rest of the service writes through, not a separate copy).
- `vinu-initial-analysis/tests/test_signal_evidence.py` -- 8 tests, with
  a hand-built `httpx.Client` fake (no real network calls): no-data/
  insufficient-data gating; a deterministically-engineered price series
  (a slow monotonic decline, then a steep monotonic ramp -- chosen so
  there's exactly one, unambiguous crossing with a non-degenerate true
  range throughout, not a coin flip on random noise) finds the crossing
  and records both the trigger and outcome POSTs with the right payload
  shape; a flat series finds zero crossings and makes zero HTTP calls; a
  crossing truncated too close to the window's end is skipped as
  incomplete, not recorded, with zero HTTP calls; a 409 response is
  counted as already-recorded, not an error, and correctly skips the
  outcome POST; a 500 response is counted as a real record error; the
  recorded outcome values are verified against the actual forward prices
  in the engineered uptrend (positive return, max-favorable >=
  return-at-horizon >= max-adverse).
- Angle discovery verified directly: a fresh `AngleRunner` in a temp
  directory discovers 29 angles including `signal_evidence` (up from the
  28 counted in Phase 1).
- `RunLog`'s v3 migration (`models_enabled` column) re-verified against
  a fresh copy of the real production database, same procedure as the
  v2 migration before it -- copy discarded after verification.
- Full `vinu-initial-analysis` regression suite (same torch-less/
  network-less exclusions as Phase 1, all independently confirmed
  pre-existing via `git stash` comparison against unmodified `main`):
  **393 passed**, zero new regressions.
- Full `vinu-infra` regression suite re-run after `ticker_coverage.py`
  took a new cross-package dependency on
  `vinu_infra.system_manifest.resolve_active_angles`: **286 passed**, no
  change.

### Known limitations / left for later

- **The LIVE detector inside `vinu-live` still doesn't exist.** This
  extension closes the historical-backfill gap, not the live-execution
  one -- Layer 5's continuous, every-cycle lookup for open positions
  still has nothing generating new triggers as they happen in real time,
  only this angle's periodic historical/backfill sweep.
- **Only 3 supporting indicators are computed by this angle** (ADX, RSI,
  volume-vs-avg20) -- a deliberate, honest scope limit, not an oversight:
  every other candidate in `all-possible-supporting-indicators.md`
  either needs data this angle doesn't have in point-in-time form (the
  28 angles' own outputs, for the look-ahead-bias reason above) or
  wasn't implemented yet (MACD, Bollinger Bands, ATR, etc. -- these are
  straightforward additions following the same ADX/RSI pattern, just not
  built in this pass).
- **`FORWARD_HORIZON_BARS` (default 20) is a guessed constant**, not yet
  derived from real data the way Decision 1's own reasoning says it
  eventually should be (median time-to-target from history) -- there's
  no historical evidence yet to derive it from, which is exactly why
  Phase 3 (bucketing/analysis) stays deferred; this angle's job right
  now is to start producing that evidence, not to already have used it
  to pick its own parameter.
- **The must-condition is hardcoded to the one running example**
  (SMA(5) x SMA(50)) -- there is still no general mechanism for a
  strategy to declare its own must-condition(s) to this angle; that's
  the same open question `00-explanation.md` already flagged
  ("where does the must-condition / supporting-indicator declaration
  actually live").

## Phase 3 -- analysis layer (Layer 4 bucketing)

**Status: not started, deliberately deferred until Phase 2 has produced
real rows (per the pending decision log in `01-planning.md`).**
