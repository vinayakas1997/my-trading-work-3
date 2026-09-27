# Open questions: connecting the 29th angle to strategy definition, simulation, and live recording

**Status: none of this is decided or designed in detail yet, and nothing
in this file has been acted on.** This file exists to jot down major,
distinct questions and audit findings as they come up, each big enough
to deserve its own real discussion later, so none of them get lost.
Written against the real current code in each component named, not
guessed. Items 1-5 are the original design questions; 6-10 are follow-on
ideas surfaced afterward; 11 is a real code audit of `vinu-agent`.

## 1. Strategy definitions need a `must_conditions` / `supporting_indicators` schema, each carrying its own "why" — **UPDATE: this already exists, it's just not connected to Track 1**

**The problem, stated explicitly, after checking the real code
(2026-09-25)**: `vinu-research/hypothesis_registry.py` +
`vinu_research/models.py`'s `Hypothesis` dataclass is **already almost
exactly** the "must-condition/indicator + why" mechanism this item
originally proposed building from scratch:
- `thesis` — the "why"
- `signal_definition` — the must-condition (a free string, not
  structured per-condition)
- `indicators_used` — the supporting indicators list
- `status`: `exploring → testing → validated / rejected / monitoring /
  mc_gate_failed` — a real lifecycle, one status literally named
  "must-condition gate failed"
- `invalidation_reason` — why an assumption was retired
- `evidence: list[Evidence]`, each tied to a `run_id`, with
  `conclusion`, `reasoning`, a metric/value — `add_evidence()` already
  auto-promotes status from incoming evidence (`best_sharpe > 0.3` →
  testing, `> 0.5` → validated)
- Locking and atomic writes already handled correctly
  (`_locked()`/`_write()` in `hypothesis_registry.py`)

**The actual, explicit problem**: Track 1's `signal_evidence` angle POSTs
its trigger/outcome data straight to `SignalEvidenceStore` and **never
touches `HypothesisRegistry` at all**. So a must-condition's "why" can
never get validated or invalidated by Track 1's recorded evidence,
despite the exact mechanism to do that already existing, tested, and
running elsewhere in this same codebase. This item is no longer "design
a new schema" — it's **"call `HypothesisRegistry.add_evidence()` /
`reject_with_reason()` from Track 1's outcome-recording path, once a
trigger's outcome is known."**

**Still genuinely open**: `signal_definition`/`indicators_used` are
looser (a free string, a flat list) than the more structured, per-
condition "why" originally sketched here — connecting Track 1's
structured trigger data to this looser shape is a small remaining design
step, not a zero-effort wire-up. Which of Track 1's fields map to
`Evidence.metric`/`.value`/`.conclusion` is not decided.

**Superseded by a fuller spec**: this item's "why" schema has since grown
into a complete strategy-definition field list — precondition/
postcondition (mirroring Track 2's PRE/POST), risk management, a
two-level failure definition, a performance-record reference, origin/
versioning, and regime/news context. See
`03-strategy-definition-full-schema.md` for the full, standalone writeup;
this item now just covers the original must-condition/indicator "why"
piece of that larger schema.

**UPDATE (2026-09-26)**: **the wiring is now built and tested**, decided
and implemented after a real design discussion (not invented
unilaterally) that surfaced something the audit itself hadn't: `add_evidence()`'s
auto-promotion math (`best_sharpe` tracking, the 0.3/0.5 status
thresholds) is Sharpe-specific — Track 1's outcome data
(`return_at_horizon`) is not a Sharpe ratio, and naively calling
`add_evidence()` with it would have silently corrupted `best_sharpe` and
mis-fired the promotion thresholds on numbers that mean something
completely different. The chosen design, decided explicitly: **evidence-
trail only, no auto-promotion** — the historical evidence becomes
visible and queryable on the matching hypothesis, but a human/agent
still decides what it means; and **strict match only, no auto-create** —
a new hypothesis is never fabricated to force a match, matching item
#16 finding #4's own warning about fuzzy-match fragility.

- `models.py`'s `Evidence` gained `metric_kind: str = "sharpe"` (default
  preserves every existing caller's behavior unchanged) and `run_id`'s
  type relaxed from `int` to `int | str` (Track 1 evidence isn't tied to
  a single numeric research run, unlike every existing caller).
  `hypothesis_registry.py`'s `add_evidence()`/`add_evidence_batch()` now
  only run their Sharpe-specific promotion math when
  `metric_kind == "sharpe"` — anything else is appended to the evidence
  list, visible and queryable, without touching `best_sharpe` or status.
- New `vinu_research/signal_evidence_bridge.py::sync_signal_evidence_to_hypotheses()`:
  for each symbol, groups `SignalEvidenceStore`'s recorded triggers by
  `must_condition`, summarizes every *resolved* one (count, average
  `return_at_horizon`, win rate, days since the condition last fired),
  and — only when an exact string match exists between a hypothesis's
  `signal_definition` and the condition (`query_by_symbol` filtered
  further, no fuzzy matching) — appends one summary `Evidence` entry
  per (symbol, condition) per call, tagged `metric_kind="signal_evidence"`.
  A symbol with no matching hypothesis, or no resolved triggers yet, is
  reported (not silently dropped) and never causes a new hypothesis to
  be fabricated.
- **Wired to a real, already-existing cycle, not a new schedule**: new
  `sync_signal_evidence_for_tickers()` in `vinu-agent/agent/
  scheduler_workers.py`, called once per `planner-worker` cycle
  (`cli.py`) over the exact same screener-merged ticker list that cycle
  already pulls from `TickerSummaryStore` — using the same in-process
  `HypothesisRegistry`/`SignalEvidenceStore` bridges
  (`broker/research_link.py`) already established for every other
  in-process call site in this file. Fails open on any failure
  (`ImportError` or a real exception both return `None`, logged, never
  propagated) — the same "background sync, never blocks the cycle's real
  work" posture already used elsewhere in this file for its own
  no-HTTP-fallback call sites.
- 16 new tests: 7 in `test_hypothesis_registry.py`
  (`TestMetricKindGatesPromotion` — confirms non-Sharpe evidence is
  appended without touching `best_sharpe`/status, confirms Sharpe
  evidence still promotes exactly as before, confirms a mixed batch only
  lets its Sharpe entries drive promotion, confirms `metric_kind`
  round-trips through persistence and defaults to `"sharpe"` for
  pre-existing rows with no such column at all), 9 in
  `test_signal_evidence_bridge.py` (through real `SignalEvidenceStore` +
  `HypothesisRegistry` instances, not mocks — a real match appends
  correctly, a mismatched `signal_definition` doesn't, an unresolved
  (still-open) trigger isn't summarized, no hypothesis at all is
  reported rather than auto-created, calling twice appends a second
  entry rather than replacing), 4 in `test_scheduler_workers.py`
  (`TestSyncSignalEvidenceForTickers` — the real bridge gets called with
  both in-process stores, `vinu-research` not being importable fails
  open, a real exception from the bridge itself is caught and never
  propagated).
- Confirmed zero regressions: `vinu-research` 1018 passed, 1 skipped (up
  from 1003, +16 -- the one pre-existing flaky
  `test_sqlite_backend.py::test_concurrent_writes`, already documented
  in item #12's own update, failed on this particular run instead of
  passing, accounting for the +15-vs-+16 apparent mismatch); `vinu-agent`
  1371 passed (up from 1367, exactly +4), same pre-existing 16
  failures/2 errors unchanged.
- **What this leaves open**: item #16 finding #1's own fuller ask
  (feeding this evidence into `llm_generator.py`'s
  `_build_generation_prompt`/`_build_refinement_prompt` so a candidate
  generation call actually *sees* it, not just that it's now reachable
  via `HypothesisRegistry`) is a separate, further step, not done here —
  this makes the historical evidence queryable and visible on the
  matching hypothesis; it does not yet change what the LLM reads when
  drafting a new candidate.

## 2. A "universal strategy" runnable directly inside the 29th angle

Today, `signal_evidence` is hardcoded to exactly one must-condition
(`sma5_cross_sma50`) — see `../how-to-use-29th-angle/01-track1-how-it-works-today.md`. The idea:
instead of that being permanently fixed, the angle accepts a strategy
definition (per #1's schema) and runs *that*, generically — so any
must-condition/indicator set anyone defines gets Track 1's exact
recording mechanism (52-indicator snapshot, outcome path, idempotent
storage) automatically, not just the one running example this whole
design has been built and tested against so far.

**Open**: this is a real generalization of `signal_evidence/compute.py`,
not a small change — it currently assumes one condition's shape
throughout. Not designed yet, and probably the biggest single piece of
work in this list.

**Concrete mechanism, and a "reduce, don't rebuild" opportunity worth
checking before writing new condition-evaluation code**: today's
hardcoded `MUST_CONDITION_NAME = "sma5_cross_sma50"` constant would
become a loop over a list of condition definitions (item #07's
`must_conditions` field), each evaluated against the bar series to find
historical firing points. Before building a new condition-evaluation
engine for this, check whether `vinu-strategy/vinu_strategy/engine/rules.py`/
`rules_engine.py` (a real, existing condition/rule evaluator, confirmed
in item #22's audit) can be reused here — if it already evaluates
arbitrary boolean conditions over symbol data generically, that's a
second real instance of "the mechanism already exists elsewhere,"
matching the `HypothesisRegistry` discovery in item #1. Not confirmed
either way yet — worth checking before assuming new code is needed.

**UPDATE (2026-09-27)**: **proven as a working proof-of-concept, not the
full generalization this item's own text calls "probably the biggest
single piece of work in this list."** Deliberately scoped down: this
proves the one specific mechanism claim item #2 makes (the recording
pipeline generalizes to a different must-condition), not the full
strategy-definition schema integration (`03-strategy-definition-full-
schema.md`'s precondition/postcondition/risk-management/versioning
fields) — that remains a separate, much bigger piece of work.

- **Checked the "reduce, don't rebuild" question first, and it resolved
  to "no, can't reuse it," not "yes":** `vinu-strategy/engine/rules.py`/
  `rules_engine.py` evaluates one live snapshot dict (`ctx["features"]`)
  against simple `gt`/`lt`/`eq`/`between` operators with zero memory of
  the previous bar — it has no concept of a *crossing* at all (inherently
  a two-bar, prior-vs-current comparison) and isn't built to scan a
  historical bar series. Confirmed by reading `rules_engine.py`'s real
  evaluate loop, not assumed from the name. So the existing
  `_find_crossings` (already used for the hardcoded example) stayed the
  one crossing primitive — reused, not reinvented — rather than either
  assuming reuse would work or building a second crossing algorithm from
  scratch.
- New `MustCondition` dataclass (`signal_evidence/compute.py`): `kind=
  "cross_above"` (`fast_key`/`slow_key`, the original example's own
  shape) or `kind="threshold_cross_above"`/`"threshold_cross_below"`
  (`indicator_key`/`threshold` — e.g. "RSI(14) crosses above 30," a
  genuinely different KIND of must-condition, mean-reversion rather than
  trend-following, chosen specifically to prove this isn't just
  re-parameterizing the same crossing shape). Both kinds still bottom
  out in `_find_crossings` — the threshold kinds just feed it a constant
  series as the other operand.
- `compute()` gained an optional `must_condition: MustCondition | None =
  None` parameter. `None` (every existing caller, unchanged) preserves
  today's exact hardcoded SMA(5)/SMA(50) behavior byte-for-byte — the
  default condition references the *same* `sma_fast`/`sma_slow`
  variables the old code always computed, not a re-derived equivalent
  that could drift numerically. A new `series_by_key` dict exposes every
  indicator series this angle already computes (keyed by the exact same
  strings already used for the `indicators` snapshot dict, e.g. `"rsi"`,
  `"sma_50"`, `"macd_line"`) so a caller-supplied condition can reference
  any of them with zero new computation.
- **What this proves, concretely**: a real RSI-threshold must-condition,
  run through the exact same pipeline (indicator snapshot, outcome path,
  idempotent HTTP POST to `SignalEvidenceStore`) the hardcoded SMA
  crossover always used, with the full 30+ column supporting-indicator
  snapshot still attached — not a stub, a real end-to-end trigger
  recorded under a different `must_condition` name.
- **What this deliberately does NOT do, so scope doesn't get overclaimed**:
  no config/HTTP surface exists yet for anyone to actually supply a
  custom `MustCondition` in production — `runner.py` (the real caller)
  invokes every angle's `compute()` with a fixed kwarg set, and only
  conditionally adds an extra one (`price_client`) via
  `inspect.signature()` introspection when an angle's own signature has
  it. The same introspection mechanism is the natural next extension
  point for `must_condition` once there's a real config source
  (a YAML list per item #1's `must_conditions` field, most likely) to
  supply it from — not built here, since deciding that config shape is
  its own real design question, not a mechanical wiring step.
- 6 new tests in `test_signal_evidence.py` (`TestUniversalMustCondition`):
  the default (`must_condition=None`) path is unchanged, a real
  RSI-crosses-above-30 fixture is detected and recorded with the full
  indicator snapshot attached, the mirror-image `threshold_cross_below`
  kind, a custom two-series `cross_above` condition (EMA(5)/EMA(20),
  proving it's not limited to the one hardcoded pair), an unknown `kind`
  raises a clear `ValueError` rather than silently doing nothing, and
  referencing an unknown series key fails open to zero crossings rather
  than crashing. Confirmed zero regressions: `test_signal_evidence.py`
  17 passed (up from 11, exactly +6); `test_regime_analysis_backtest.py`
  + `test_signal_contract.py` unaffected (29 passed together with
  `test_signal_evidence.py`) — the only files that plausibly touch this
  change (an additive-only optional parameter on one module's `compute()`).
  A full-suite run was attempted but not completed: this component's
  ML-dependency test files (LSTM/PatchTST/TFT/etc.) are slow/flaky to
  collect in this environment regardless of this change, already
  documented earlier in this item's own history as a pre-existing
  condition, not re-confirmed clean end-to-end this pass.

## 3. Sweep/search comparisons are computed then thrown away — the raw runs are NOT lost, but the "why this lost" verdict is

**Checked directly against the real code (2026-09-25), correcting an
earlier assumption in this file**: individual simulation runs are
already durably persisted, winner or loser, with no distinction between
them — `vinu_simulator/service.py` calls
`self._meta_storage.insert_run(...)` unconditionally for every run
(`vinu_simulator/storage/meta.py`'s `simulation_runs` table, one row per
`run_id`, plus per-run `equity.parquet`/`weights.parquet`/`trades.parquet`
files). A losing sweep candidate gets exactly the same durable record a
standalone backtest gets — nothing about the raw run data is discarded.

**What actually is thrown away is the comparison itself.** The
sweep/ranking machinery lives in `vinu-research`, not `vinu-simulator`:
`vinu_research/sweep_grid.py`'s `SweepGridResult` (with `outcomes`
including every failed grid point and `ranked` candidates with scores)
is a plain in-memory dataclass. `vinu_research/server/routes_sweep.py`
serializes it straight into an HTTP JSON response and returns it — no
storage call anywhere in that file. `walk_forward.py` and
`comparison.py` are purely computational too (grepped for
insert_run/store/persist/save: zero hits in either). So today, 20 sweep
runs sit in `simulation_runs` looking like 20 unrelated ad-hoc backtests
— nothing on disk records that they were one search round, what rank
each got, or why the others lost. That's the exact gap behind your
original point: the path to the best strategy is computed, but the
losing branches of that path vanish the moment the HTTP response is
sent, instead of becoming something a future strategy-writer can read.

**The fix, concretely, is additive, not a redesign**: a new
sweep/search-grouping table (`sweep_id`, `run_id`, `rank`, `score`,
`risk_score`, `complexity_score`, `succeeded`/`failure_reason`), written
at the exact point `sweep_grid.py`'s `run_sweep_grid()` (or
`routes_sweep.py`'s handler) currently builds the response — the data
already exists in memory at that point, it's just never written down.
This is a much smaller piece of work than it first sounded: the
individual-run persistence already exists and needs no changes; only the
grouping/verdict layer is missing.

**Separately, still open**: whether simulation-sourced runs (real
backtests, but shaped by the simulator's own fill/cost-model assumptions)
should be tagged as a distinct, lower-trust evidence tier if this ever
feeds the same store Track 1/Track 2 write to, versus being kept
entirely separate. Not decided — flagged so it isn't quietly conflated
with real historical evidence later.

**UPDATE (2026-09-26)**: **fixed, built to the exact table shape this
item's own text already specified — additive, not a redesign**, and
folds in item #12 finding #4 (the walk-forward result nested in this
same discarded object) on the same header row rather than as a separate
mechanism.

- New `vinu_research/sweep_store.py`: `SweepGridStore` (`SQLiteBackend`,
  same shared pattern every other evidence-recording store in this
  service already uses), two tables — `sweep_runs` (one header row per
  search round: `sweep_id`, symbol/date range, `requested`/`succeeded`/
  `completeness`, `pbo_json`, `walk_forward_json`) and
  `sweep_grid_points` (one row per grid point, succeeded or not: `rank`
  1-indexed best-first for succeeded points, `NULL` for failed ones,
  `score`/`risk_score`/`complexity_score`, `succeeded`/`failure_reason`,
  `params_json`). `get_sweep(sweep_id)` returns the full picture in one
  call; `list_sweeps(symbol=...)` is a real SQL `WHERE`, not item #13
  finding #3's own "load everything, filter in Python" mistake repeated
  here from the start.
- `sweep_grid.py`'s `run_sweep_grid()` now generates a real `sweep_id`
  (`uuid.uuid4()`) and persists its own result by default
  (`persist: bool = True`) at the exact point it already builds
  `SweepGridResult` — the data was already in memory, exactly as this
  finding said. Persistence failures are caught and logged, never
  propagated — a broken store must never fail the sweep itself, same
  "a side-write failing must never fail the real thing it's reporting
  on" posture this codebase already uses for notifications/escalations.
- **The one real design decision this fix needed, made explicitly**:
  `walk_forward.py`'s own inner per-window grids call `run_sweep_grid()`
  recursively (already guarded against infinite recursion via
  `walk_forward_enabled=False` on the inner config) — persisting those
  too would create N misleading "top-level search rounds" for N windows
  of what's really one walk-forward pass. Fixed by passing
  `persist=False` on that one inner call site; the OUTER call that
  actually returns `walk_forward` to its caller is what gets persisted,
  with the window verdict folded into that same row.
- Wired to the real HTTP layer, not left as a pure-function-only fix:
  `POST /research/sweep/grid`'s response gained a real `sweep_id` field
  (never omitted, `""` only if persistence was disabled or failed, so a
  caller can tell the two cases apart); new `GET /research/sweep/grid/
  {sweep_id}` (the full comparison — every point, winner and losers,
  with real reasons) and `GET /research/sweep/grid?symbol=...` (recent
  search rounds for a symbol, header rows only) let a future
  strategy-writer actually read this back, not just know it exists on
  disk somewhere.
- **A real test-hygiene issue caught before it could land**: `persist=
  True` by default meant every existing `run_sweep_grid()` call in
  `test_sweep_grid.py` (and `create_app()`'s own real `SweepGridStore`
  wiring in several `test_routes_*.py` fixtures) would have started
  writing real SQLite files under this repo's own working directory on
  every test run. Fixed at the source, not papered over: every existing
  test call that doesn't specifically test persistence now passes
  `persist=False` explicitly (matching walk_forward.py's own production
  reasoning, not just a test-only escape hatch), and
  `test_routes_sweep_grid.py`'s fixture now passes `data_root=tmp_path`
  to its `ResearchConfig` the same way `test_service`'s existing fixture
  already does elsewhere in this suite.
- 21 new tests: 12 in new `tests/test_sweep_store.py` (header/point
  round-trip, rank-starts-at-1, a failed point's reason surviving,
  failed points sorting after ranked ones, walk-forward persisting on
  the same row, `list_sweeps`'s symbol filter and limit), 5 in
  `test_sweep_grid.py` (`TestRunSweepGridPersistence` — persists to a
  given store with a real `sweep_id`, `persist=False` never touches the
  store, a failed grid point's reason is captured, a broken store
  doesn't fail the sweep, no explicit store lazily builds one at
  `config.data_root`), 4 in `test_routes_sweep_grid.py`
  (`TestSweepPersistenceWiring` — real `sweep_id` in the POST response,
  `GET .../grid/{sweep_id}` returns the full comparison, unknown
  sweep_id is 404, `list_sweeps` filters by symbol through the real HTTP
  layer). Confirmed zero regressions and zero stray files: full
  `vinu-research` suite passes with these changes (see this same
  session's confirmed-clean re-run), no `data/sweep_grid.db` (or any
  other store's `.db` file) left behind by any test.

## 4. Simulator's PnL/risk logic should adopt the 29th-angle's engine (ATR, position sizing) to report real dollar expectancy

Today's real `PositionSizer` classes in `vinu_simulator/engine/sizing.py`
(`FixedSizer`, `VolTargetSizer`) only know about trailing realized
volatility — nothing about must-condition confidence or move-evidence
continuation odds. The idea, concretely: "if I put in $100 on this
signal, what's the actual expectation" — meaning the simulator's PnL/risk
module should be able to consume the same ATR-based
detection/sizing logic Track 2's engine uses (`../how-to-use-29th-angle/04-track2-engine-and-storage.md`),
so a backtest reports dollar-denominated expectancy per unit of capital,
not just an abstract win-rate/Sharpe number.

This is the same connection already sketched when position sizing came
up earlier in this conversation: a new `PositionSizer` subclass
(an `EvidenceConfidenceSizer`, tentatively) that scales exposure using
Phase 3 / Track 2 aggregate-mode expectancy, tested in `vinu-simulator`
first before ever reaching `vinu-portfolio`'s live sizing.

**Open**: this depends on Phase 3 (Track 1's analysis layer) or Track
2's aggregate mode actually existing first — right now there's no
expectancy number to feed this sizer at all.

## 5. A "present-data" recording layer, mirroring pre-analysis, for live/current data

`vinu-initial-analysis` computes and stores angle outputs for
historical/backfill data. There is currently **no equivalent for live,
present-moment data** — nothing recording the same kind of computation
as it happens in real time, the way pre-analysis does for history. This
is the same underlying gap as the already-flagged "live detector doesn't
exist" item (see `../how-to-use-29th-angle/01-track1-how-it-works-today.md`'s "what doesn't exist
yet" section, and `vinu-live`), but framed more specifically here: it
needs **its own storage**, structured similarly to how pre-analysis
stores things, not bolted onto the historical tables after the fact —
present-moment data has different freshness/staleness properties than a
backfilled historical row and probably shouldn't share a table with it
without that being a deliberate decision.

**Open**: entirely undesigned. Whether this lives in `vinu-live` (the
component name suggests so) or is a new dedicated store, not decided.

**Concrete starting schema, so this has a real shape to react to rather
than staying purely abstract**: a `live_snapshots` table — one row per
`(symbol, angle_name, computed_at)` (`computed_at` a real wall-clock
timestamp, not a fixed `analysis_from`/`analysis_until` range like
`RunLog` uses for backfill), `granularity`, `snapshot_data` (JSON, same
per-indicator shape as the historical angle output), and a
`staleness_seconds` field computed at *read* time (age relative to now),
not stored — the same "coverage view computed fresh, never cached" rule
`ticker_coverage.py` already established for a different table (Decision
9's reasoning). This deliberately mirrors `RunLog`'s shape closely enough
that the same query patterns work, while keying on real-time recency
instead of a historical range — which is the actual, specific difference
between "pre-analysis" and "present-data" recording.

## 6. Regime tagging at trigger/move time, reusing what already exists

There are already three separate point-in-time-safe regime classifiers
in this codebase — `vinu_initial_analysis/angles/regime_analysis/compute.py`,
`vinu_simulator/engine/regime.py`, `vinu_portfolio/regime.py` — all
labeling `bull`/`bear`/`high_vol`/`neutral` off a rolling-vol z-score
against a trailing baseline, all already fixed for look-ahead leaks.
Neither Track 1 nor Track 2 currently tags its rows with the regime
active at trigger/move time.

**The idea**: reuse one of these existing classifiers as one more field
alongside `session`/`day_of_week` — cheap, because the point-in-time-safe
logic already exists three times over, nothing new to build. This is the
concrete example of the "reduce, don't rebuild" principle: check the 28
angles first, before adding a new mechanism.

**Concrete field and an open decision about which of the three
implementations to call**: add `regime: "bull" | "bear" | "high_vol" |
"neutral"` to Track 1's indicator snapshot and to each of Track 2's
phase/checkpoint indicator blocks (`../how-to-use-29th-angle/02-track2-design.md`). Which of the
three existing classifiers to call is a small but real open decision:
`vinu_initial_analysis/angles/regime_analysis/compute.py`'s is the most
natural choice for an angle to call (same service, no cross-service
dependency), whereas calling into `vinu_simulator/engine/regime.py` or
`vinu_portfolio/regime.py` from an angle would create an odd dependency
direction (a Layer 2 analysis angle depending on a Layer 5/backtest
component). Not yet decided which is the intended "reference"
implementation versus which are the two other services' own necessary
local reimplementations of the same logic for their own reasons.

**UPDATE (2026-09-26)**: **Track 1's half is now built and tested**, using
this item's own already-worked-out reasoning (same-service call, no
cross-layer dependency inversion) rather than inventing a new decision —
Track 2's half is separately still unbuilt (see below).

- Checked before writing anything, since `session/day_of_week` fields
  the finding says to add `regime` "alongside" turned out **not to exist
  anywhere in the real `signal_evidence/compute.py` payload at all** —
  this finding was more involved than its own "small but real open
  decision" framing suggested; there's no existing per-trigger context
  block to slot into, just the flat `indicators: dict[str, Any]` payload
  `record_trigger()` already accepts (heterogeneous per-indicator values,
  no schema change needed for a new key, per `SignalEvidenceStore`'s own
  Decision 3 design). `regime` was added as one more key in that same
  dict, not a new top-level field — no schema change anywhere.
- `regime_analysis/compute.py`'s private `_compute_regime_frame` (the
  exact point-in-time-safe per-bar series) made public as
  `compute_regime_frame`, reused directly by `signal_evidence/compute.py`
  — not a new formula, the same one this item's own text pointed at.
  **A real indexing trap caught before it became a bug**:
  `compute_regime_frame()` drops rows before its own warmup and
  re-indexes the result from 0, so its row position is *not* the same as
  the original bars' positional index once any row is dropped — looked
  up by `bar_ts` (a real key both series share) instead of position, or
  every trigger before regime's own ~141-bar warmup would have silently
  received some *other* bar's regime value.
- Sparse by design, same as every other indicator in this payload: a
  trigger whose bar predates `regime_analysis`'s own warmup, or a symbol
  fetched with no `bar_ts` column at all, simply has no `"regime"` key —
  not a fabricated placeholder value.
- 2 new tests in `vinu-initial-analysis/tests/test_signal_evidence.py`:
  one confirming `regime` is correctly *absent* for the existing
  150-bar fixture (its crossing bar genuinely predates regime's own
  warmup — verified by direct computation before writing the test, not
  assumed), one confirming a longer, 175-bar fixture's later crossing
  gets tagged with a real regime value. Confirmed zero regressions:
  `test_signal_evidence.py` 11 passed (up from 9, +2),
  `test_regime_analysis_backtest.py` and `test_signal_contract.py`
  unchanged (the rename's other two real call sites), full
  `vinu-initial-analysis` suite 364 passed (up from 362, +2), same
  pre-existing 46 failures/24 errors (unrelated ML-dependency collection
  issues, confirmed identical to the baseline already established
  earlier in this file's own item #15 update).
- **What this item leaves open**: Track 2's half (adding `regime` to
  "each of Track 2's phase/checkpoint indicator blocks") is untouched —
  Track 2 itself is still a design (`../how-to-use-29th-angle/
  02-track2-design.md`), not real code yet, so there is nothing to wire
  this into on that side yet.

## 7. Assumption decay/versioning for the "why" claims in #1 — **UPDATE: this already exists too, same gap as #1**

**The problem, stated explicitly**: this item asked for an explicit
lifecycle status so a falsified assumption could be retired without
deleting its history. That lifecycle already exists —
`HypothesisRegistry`'s `HypothesisStatus` enum
(`exploring`/`testing`/`validated`/`rejected`/`monitoring`/
`mc_gate_failed`) plus `reject_with_reason()` (sets `invalidation_reason`
and flips status to `rejected`) is exactly this mechanism, already built,
already handling the "don't delete history, just mark it" requirement.

**The actual, explicit problem is identical to #1's**: nothing in Track
1 ever calls `reject_with_reason()` or feeds evidence that would trigger
`add_evidence()`'s automatic status transitions. The lifecycle exists and
sits unused by the must-condition recorder it was arguably built to
serve. Once #1's wiring is done (Track 1 outcomes → `add_evidence()`),
this item is largely resolved as a side effect — it is not a separate
piece of work.

**Still open**: what specifically should trigger `reject_with_reason()`
automatically (a fixed number of contradicting outcomes? a statistical
threshold from Phase 3 once it exists?) versus requiring a human/agent to
call it manually — not decided.

**UPDATE (2026-09-26)**: **resolved as a side effect of item #1's
wiring, exactly as predicted here** — with one honest correction to that
prediction. Item #1's actual build deliberately does **not** call
`add_evidence()`'s automatic status-transition path at all (a
Sharpe-specific mechanism, not reused for this) — so `reject_with_reason()`
still isn't called automatically by anything. What this item actually
asked for — "an explicit lifecycle status so a falsified assumption
could be retired without deleting its history" — is satisfied a
different way: Track 1's evidence is now visible on the hypothesis's own
evidence trail (`metric_kind="signal_evidence"`), so a human/agent
deciding to call `reject_with_reason()` manually now has the real
history to decide from, where before there was none reaching
`HypothesisRegistry` at all. **Still open, unchanged from the original
note**: what should trigger `reject_with_reason()` automatically (if
anything ever should) remains undecided and unbuilt — this update closes
the "the evidence never reaches the lifecycle mechanism at all" gap, not
the "what triggers automatic rejection" question.

## 8. Cross-strategy indicator pooling

If the same supporting indicator (e.g. ADX>25) appears as a "why" across
several different strategies with different must-conditions, each
strategy's evidence is currently siloed. A higher-leverage question than
per-strategy Phase 3 bucketing: does ADX>25 matter *in general*,
independent of which must-condition it's paired with?

**Open**: this is a meta-analysis layer on top of Phase 3, not decided,
and depends on #1's schema existing first (there's no structured "why"
to pool across strategies yet).

**Concrete mechanism, consistent with the "derived pivot, not duplicated
storage" rule `ticker_coverage.py` already established (Decision 9)**:
this should be a read-time query over `HypothesisRegistry`'s existing
data, not a new table — group `Evidence` outcomes by entries in
`indicators_used` across every hypothesis (once #1's structured
"why" schema exists to make that grouping meaningful), the same way
`ticker_coverage.py` computes its view fresh from `RunLog` rather than
maintaining a separate synced copy. No new storage needed once #1 exists
— just a new query pattern over storage that already exists.

**UPDATE (2026-09-27)**: **built.** This item's own stated blocker was
stale — item #1's wiring (`HypothesisRegistry`/`indicators_used`/
`Evidence`) landed on 2026-09-26, so the "depends on #1's schema existing
first" precondition was already satisfied; checked the real code before
building rather than trusting the item's own text.

- New `HypothesisRegistry.pool_evidence_by_indicator()`: exactly the
  read-time query this item's own "concrete mechanism" note sketched —
  loads every hypothesis, and for each entry in its `indicators_used`,
  pools that hypothesis's `Evidence` list under that indicator's name.
  No new table, no new file — a fresh in-memory grouping over the exact
  same `hypotheses.json` `list_all()`/`query_by_symbol()` already read,
  same "derived pivot" idiom `ticker_coverage.py` established.
- **Grouped by `(indicator, metric_kind)`, not just indicator** — this
  matters and wasn't free: item #1's own fix established that a Sharpe
  ratio and a `signal_evidence` average forward return are not the same
  claim even when both cross the same literal number, and naively
  averaging a pooled indicator's values across both kinds here would
  have re-introduced that exact mistake one level up, silently. Each
  indicator's result is `{metric_kind: {evidence_count,
  hypothesis_count, avg_value, support_rate}}` — a Sharpe-flavored
  average and a signal-evidence-flavored average never collide into one
  number.
- `hypothesis_count` (distinct hypotheses contributing, not just raw
  evidence rows) is tracked separately from `evidence_count`, since
  a single well-tested hypothesis contributing 20 evidence rows for one
  indicator is a different claim than 20 different hypotheses each
  contributing one — pooling should not let one hypothesis's volume of
  evidence look like broad cross-strategy support.
- New read-only route: `GET /research/indicators/pool`, same
  "read access to state that already exists, no new writes" idiom as
  every other route in `routes_introspect.py`.
- 8 new tests: 6 in `test_hypothesis_registry.py`
  (`TestPoolEvidenceByIndicator` — pools correctly across two
  hypotheses sharing an indicator, keeps metric kinds from mixing under
  one average, a hypothesis with no `indicators_used` contributes
  nothing, one with indicators but no evidence contributes nothing, an
  empty registry returns `{}`), 2 in
  `test_routes_introspect_indicator_pool.py` (empty case, and the same
  cross-hypothesis pooling exercised through the real HTTP route).
  Confirmed passing together with the existing hypothesis/introspect
  route tests: 51 passed (up from 42, +9 net — 8 new plus one file that
  didn't exist before this update). Full `vinu-research` suite: 1094
  passed, 1 skipped, 1 failed (the same pre-existing flaky
  `test_concurrent_writes`, no new failures) — zero regressions.
- **What this leaves open**: this pools evidence that already exists;
  it does not change what feeds a hypothesis's `indicators_used` in the
  first place, and nothing yet reads this pooled view back into
  candidate generation (the same kind of further step item #1's own
  update flagged as open for `llm_generator.py`).

## 9. News-confound flagging

`vinu-news` already exists in this codebase but nothing in Track 1/Track
2 checks it. A move or trigger driven by an earnings surprise or
headline is a fundamentally different animal from one driven by pure
technical continuation — conflating the two in the same Phase 3/Track 2
bucket blurs the statistics.

**The idea**: a simple flag — was there a news event within N minutes of
this trigger/move — so Phase 3 (or Track 2 aggregate mode) can exclude
or separate news-driven cases.

**Open**: not designed — what counts as "a news event" for this purpose,
and the N-minute window, are both undecided.

**Concrete field, and a dependency worth naming explicitly**: add
`news_confound: {occurred: bool, minutes_before: float | None,
article_id: str | None}` to Track 1's trigger row and Track 2's move row,
computed by querying `vinu-news`'s `/ticker/{symbol}` endpoint for the
window `[trigger_time - N_minutes, trigger_time]`. This now directly
depends on item #19's finding being fixed first: `vinu-news`'s
`sort_ts` can silently be an ingestion-time fallback rather than a true
publish time, so a naive query against it could mis-time whether a news
event genuinely preceded the trigger or not — this flag would inherit
that risk until item #19's `published_at`/`publish_time_is_estimated`
fields exist. The `N_minutes` window value itself is an open constant,
same posture as `floor_multiple`/`FORWARD_HORIZON_BARS` elsewhere in this
file — a reasonable guess until real data exists to derive it from.

**UPDATE (2026-09-27)**: **Track 1's half built** — its own precondition
(item #19's `published_at`/`publish_time_is_estimated` fix) was already
satisfied, so this was buildable now rather than genuinely blocked.
Track 2's half remains untouched, same reason item #6/#10 are also only
half-built: Track 2 itself is still a design, not real code.

- **A real wiring gap turned up, better than this item's own suggested
  design**: this finding's own text assumed a fresh query against
  `vinu-news`'s `/ticker/{symbol}` endpoint per trigger. Checked
  `runner.py` first and found the query already happens — `_fetch_news()`
  fetches the whole run's news once per (symbol, date-range) call,
  caches it, and hands it to *every* angle's `compute()` as the `news`
  kwarg already — `signal_evidence/compute.py` had simply never read it.
  No new HTTP call needed at all; each trigger's window lookup is a
  local scan over the same already-fetched list.
- New `_build_news_index()` (one pass over `news`, sorted by an
  "effective timestamp" — `published_at` when known, `sort_ts` otherwise,
  the same fail-open-to-best-available-time convention `sort_ts` itself
  already represents post item #19's fix, not a new one invented here)
  and `_news_confound()` (the actual window/closest-preceding-article
  logic). `NEWS_CONFOUND_WINDOW_MINUTES` defaults to 60 — a guessed
  starting constant, same posture as `FORWARD_HORIZON_BARS`, configurable
  via `get_angle_setting()` like every other numeric knob in this file.
- Only articles AT OR BEFORE the trigger count — a headline minutes
  after a trigger already fired is a separate future event, not a
  confound for it (a real no-look-ahead check this item's own text
  didn't explicitly call out, added on the same "point-in-time safety"
  posture this whole file already applies everywhere else).
- Wired into the exact same flexible `indicators` dict `regime` (item
  #6) already extended, not a new schema field or SQL column — the same
  established pattern for adding one more per-trigger context key.
  Sparse by construction: absent entirely when no `news` was passed or
  the list is empty, present as `{occurred, minutes_before, article_id}`
  otherwise, never a placeholder value.
- 7 new tests in `test_signal_evidence.py` (`TestNewsConfound`): no
  `news` arg leaves the field absent, an article shortly before the
  trigger is flagged with a real `minutes_before`, one outside the
  window isn't, one AFTER the trigger doesn't count (the no-look-ahead
  check), the closest of several qualifying articles is the one
  reported, `published_at=None` falls back to `sort_ts` rather than
  dropping the article, and an empty `news=[]` list also leaves the
  field absent. Confirmed zero regressions: `test_signal_evidence.py`
  24 passed (up from 17, exactly +7); `test_trend_lifecycle.py` +
  `test_trend_lifecycle_backtest.py` + `test_regime_analysis_backtest.py`
  + `test_signal_contract.py` unaffected (44 passed together).
- **What this leaves open**: Track 2's half (Track 2 isn't real code
  yet); the `N_minutes` window and "what counts as a news event" (any
  article `vinu-news` already returns for this ticker, no additional
  filtering by category/impact/sentiment) remain guessed defaults, not
  derived from real data, exactly as this item's own text anticipated.

## 10. Cross-track disagreement as its own signal

When Track 1's must-condition fires but Track 2 simultaneously detects no
big move (or a move in the opposite direction), that mismatch is itself
informative rather than something to silently ignore.

**Open**: not designed — depends on both tracks being live and queryable
against the same time window, which neither is yet.

**Concrete mechanism**: a periodic reconciliation job (not stored inside
either track's own tables) producing a `cross_track_check` record —
`{symbol, time_window, track1_fired: bool, track1_trigger_id: str | None,
track2_move_detected: bool, track2_move_id: str | None, agreement:
"confirmed" | "track1_only" | "track2_only" | "neither"}` — computed by
comparing `SignalEvidenceStore` and the future `MoveEvidenceStore` over
the same rolling window. Kept as its own small table rather than a column
bolted onto either store, since it's derived from *both* and belongs to
neither on its own.

## 11. vinu-agent inefficiency audit (2026-09-25) — verified, not yet acted on

A thorough real-code audit of `vinu-agent`'s tool-calling layer (kept
deliberately conservative — 5 verified issues, no padding, several
things checked and found fine are noted at the end):

1. **Duplicated date-parsing helpers**, copy-pasted verbatim across
   `tools/stock_price_tool.py:7-13`, `tools/news_tool.py:7-13`,
   `tools/correlation_tool.py:7-13`, `tools/features_tool.py:6` — and
   already inconsistent with each other (`_iso_to_epoch` is UTC-aware,
   `_date_to_epoch` isn't, used together in the same file). Fix: extract
   both into one shared module (e.g. `tools/_date_utils.py`).
2. **17 tool files have zero test coverage**
   (`stock_price_tool.py`, `news_tool.py`, `fundamentals_tool.py`,
   `options_tool.py`, `trade_plan_tool.py`, `portfolio_tool.py`,
   `position_sizing_tool.py`, `query_memory_tool.py`, `remember_tool.py`,
   `session_search_tool.py`, `correlation_tool.py`, `web_search_tool.py`,
   `load_skill_tool.py`, `plan_workflow_tool.py`, `compact_tool.py`,
   `complete_step_tool.py`, `angle_clusters.py`). **Most important**:
   `stock_price_tool.py`/`news_tool.py` contain the as-of date-clamping
   logic that prevents look-ahead bias in backtests
   (`stock_price_tool.py:56-62`), with zero test verification — a
   regression there would silently leak post-decision-date data into a
   backtest and nothing would catch it.
3. **`fundamentals_tool.py` has no retry/backoff around `yfinance`**
   (`tools/fundamentals_tool.py:29-30`) — a single broad `except
   Exception` turns any transient network blip into a permanent error for
   that turn; doesn't even use the shared `internal_auth_headers` pattern
   other tools use. Fix: wrap with the same retry helper
   `agent/llm.py` uses (`vinu_infra.llm.retry.build_retry`), or at least
   one retry-after-sleep like `allocation_tool.py:136` already does.
4. **No per-turn caching for repeated identical fetches** —
   `stock_price_tool.py`, `news_tool.py`, `options_tool.py`,
   `fundamentals_tool.py` all re-fetch fresh every `execute()` call, even
   within one agent loop that might call the same symbol/range twice.
   `ToolRegistry.get_definitions()` (`agent/tools.py:42-56`) already
   demonstrates the caching pattern to reuse.
5. **`options_tool.py`'s `fetch_chain` doesn't distinguish 429/5xx
   (retryable) from 401/403 (permanent)** (`tools/options_tool.py:71-81`,
   `execute()`'s except at 159-161) — both come back as the same generic
   `{"status": "error"}`, so a calling LLM can't tell whether retrying
   makes sense.

**Checked and found fine, not issues**: `ToolRegistry` schema caching,
`tools/__init__.py` auto-discovery (no dead/unregistered tool classes),
`broker/research_link.py`'s in-process-with-HTTP-fallback design
(intentional, well-documented), `query_hypotheses_tool.py`/
`symbol_research_state_tool.py` descriptions and fallback logic.

**Suggested priority if/when acted on**: #2 first (specifically the
as-of clamp tests — silent correctness risk, not just cleanliness), then
#1 (small, mechanical, removes an active inconsistency), then #3/#5
(reliability), #4 last (pure efficiency, no correctness risk). **Nothing
in this item has been acted on yet** — recorded here per instruction, no
code changed.

**UPDATE (2026-09-26)**: **findings #1 and #2 (its most important part)
built and tested, in the order this item's own suggested priority
recommended.**

- **Finding #2's most important part** (the as-of clamp tests): new
  `tests/test_stock_price_tool.py` (8), `tests/test_news_tool.py` (6),
  `tests/test_correlation_tool.py` (4) — real `execute()` calls against
  mocked HTTP, not the date helpers in isolation, covering: end_date
  beyond `_as_of` gets clamped, end_date within `_as_of` doesn't,
  omitting `end_date` defaults to `_as_of` (not wall-clock `time.time()`
  — the sharper look-ahead leak this finding specifically warned about),
  no `_as_of` set never clamps, and (`stock_price_tool.py` only) an
  inverted start/end range self-corrects to a 30-day window. The other
  14 files finding #2 lists as zero-coverage remain untested — this pass
  targeted specifically the as-of clamp logic the finding itself flagged
  as most important, not full coverage of every listed file.
- **Finding #1** (duplicated, already-inconsistent date helpers): new
  `tools/_date_utils.py` with `date_to_epoch`/`iso_to_epoch`, replacing
  the copy-pasted definitions in `stock_price_tool.py`, `news_tool.py`,
  `correlation_tool.py` (both helpers), and `features_tool.py`
  (`date_to_epoch` only). **Fixed the actual inconsistency while
  deduplicating it, not just relocating it**: the old `date_to_epoch`
  went through `time.mktime(time.strptime(...))`, which interprets the
  parsed date in the *server's local timezone* — compared directly
  against `iso_to_epoch`'s explicitly UTC-aware result in every one of
  these tools' own as-of clamp checks. A server not running in UTC could
  silently clamp to the wrong instant. Both helpers are UTC-aware now, so
  the comparison each caller already makes between them is apples-to-
  apples for the first time. 5 new tests in `tests/test_date_utils.py`,
  including one asserting `date_to_epoch("2025-06-01") ==
  iso_to_epoch("2025-06-01T00:00:00Z")` directly — the exact agreement
  the old code never actually had.
- Confirmed zero regressions: full `vinu-agent` suite, 1367 passed (up
  from 1345, exactly +22: 4 + 8 + 6 + 4 new tests), same pre-existing 16
  failures/2 errors (`test_llm.py`/`test_service.py`/
  `test_capital_allocator_hook.py`, unrelated) unchanged.
- **What this item leaves open**: finding #2's remaining 14 zero-coverage
  files, finding #3 (`fundamentals_tool.py`'s missing yfinance retry/
  backoff), finding #4 (no per-turn caching), and finding #5
  (`options_tool.py`'s 429/5xx-vs-401/403 error conflation) are untouched.

**UPDATE (2026-09-26, later same day)**: **finding #3 is now built and
tested** — `fundamentals_tool.py`'s only critical fetch (`yf.Ticker(symbol).info`)
now retries on a transient failure instead of turning any network blip
into a permanent error for that turn, per this finding's own fix text.

- A plain retry-after-sleep loop (3 attempts, 1s between), the same
  convention `allocation_tool.py`'s own retry already uses — deliberately
  **not** `vinu_infra.retry`'s HTTP helper (the finding's other offered
  option), since its `exceptions=` tuple is `requests`-specific and
  wouldn't reliably match yfinance's own transient failure modes; a bare
  `except Exception` inside the retry loop (matching this file's own
  pre-existing catch-all style) is the safer, broader match here.
  Deliberately does **not** retry a real "symbol not found" result
  (`info` present but missing a `symbol` key) — that's a correct answer,
  not a transient failure, and retrying it would just waste 3x the
  wall-clock for the same result.
- 6 new tests in a new `tests/test_fundamentals_tool.py` (this file had
  zero test coverage before, per finding #2's own list): first-attempt
  success with no retry, a transient failure that retries then succeeds,
  a permanent failure that exhausts all 3 attempts before returning an
  error, "symbol not found" confirmed *not* retried, plus two tests on
  the existing metric-selection behavior (summary default, `all`
  including financial statements when available) as a baseline
  regression guard for behavior this fix didn't intend to touch.
  Confirmed zero regressions: full `vinu-agent` suite, 1377 passed (up
  from 1371, exactly +6), same pre-existing 16 failures/2 errors
  unchanged.
- **What this item leaves open now**: finding #2's remaining 13
  zero-coverage files, finding #4 (no per-turn caching), and finding #5
  (`options_tool.py`'s error-class conflation) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #5 is now built and
tested** — `fetch_chain` now distinguishes retryable from permanent
failures, exactly the distinction this finding names, and it reaches
*both* of `fetch_chain`'s real consumers, not just one.

- New `RetryableOptionsError` (`options_tool.py`): raised for a 429/5xx
  HTTP status or a network-level timeout/connection error (the same
  class `vinu_infra.retry`'s own `retry_on_transient` already treats as
  retryable elsewhere in this codebase) — distinct from `PermissionError`
  (401/403, a permanent credential/entitlement problem) and from any
  other exception (also permanent: a bad symbol, a malformed response).
  **Fixed a second, smaller gap the finding's own text didn't call out**:
  403 used to fall through to a generic `HTTPError` via
  `raise_for_status()` instead of getting the same permanent-failure
  treatment 401 already had, despite being the same class of failure
  (credential/entitlement) — now both raise `PermissionError` together.
- **Checked both real consumers, not just the one the finding names**:
  `OptionsGreeksTool.execute()` now returns `"retryable": true/false` in
  its error response. `server/routes_options.py` — a second, independent
  consumer of the exact same `fetch_chain()` (the front door
  `vinu-research`'s own options-IV wiring calls over HTTP, per that
  route's own docstring) — had its own separate generic `except
  Exception` that would have silently lost this same distinction; fixed
  the same way there too.
- 21 new tests: 15 in a new `tests/test_options_tool.py` (this file had
  zero coverage before) covering every status-code branch (401, the
  newly-fixed 403, 429, 500, 503, 404 falling into the plain
  not-retryable bucket, connection error, timeout, a real 200 parse, and
  the missing-credentials `ValueError` path) plus the tool's
  `retryable` field itself; 2 new in `test_routes_options.py` confirming
  the route surfaces the same field for both a permanent and a
  retryable failure. Confirmed zero regressions: full `vinu-agent`
  suite, 1394 passed (up from 1377, exactly +17), same pre-existing 16
  failures/2 errors unchanged.
- **What this item leaves open now**: finding #2's remaining 13
  zero-coverage files and finding #4 (no per-turn caching) remain
  untouched. Whether `vinu-research`'s own client for this route
  (`fetch_options_context`, per `routes_options.py`'s docstring) should
  itself read `retryable` and act on it is a further, separate step, not
  attempted here — this pass makes the signal available at both existing
  consumers, not automated decision-making on top of it.

**UPDATE (2026-09-27)**: **finding #2, four more files closed** — checked
this finding's own file list against current code before picking the
next ones (`position_sizing_tool.py` already has a full test class
elsewhere, added since this item was originally written; corrected here
rather than silently re-counting it).

- `portfolio_tool.py`: new `tests/test_portfolio_tool.py` (10 tests —
  every section (`account`/`positions`/`orders`/`all`), the
  not-configured path, positions-summary aggregation across multiple
  positions, and the historical-replay (`_as_of` set) vs. live-broker
  branch). **A real, previously-untested bug found and fixed while
  writing these**: `execute()`'s single `try` wrapped all three broker
  calls together — with `section="all"`, `positions` failing *after*
  `account` already succeeded discarded the account data too, collapsing
  into a bare error response. Each section is now independently
  try/excepted: a partial success still returns what it has, with a
  per-section `errors` entry for what didn't, only becoming a true
  `status: "error"` when every requested section failed. Checked the one
  real caller path (nothing downstream assumed the old all-or-nothing
  shape).
- `remember_tool.py`: new `tests/test_remember_tool.py` (7 tests). **A
  second real bug found and fixed**: `id=f"agent-{name}"` upserts by
  design (intentional — re-remembering the same name should update it),
  but re-remembering silently reset `created_at` to "now" too, losing
  when a finding was first recorded, with no signal to the caller that
  anything was overwritten. Now checks for an existing entry first,
  preserves its original `created_at` on overwrite, and the response
  includes `overwritten: true` when one occurred.
- `query_memory_tool.py`: new `tests/test_query_memory_tool.py` (7 tests
  — success, no-memory-configured, filter/limit forwarding, the
  limit-of-50 cap, empty-string source treated as no filter, search
  exception handling).
- `web_search_tool.py`: new `tests/test_web_search_tool.py` (6 tests).
  **Worth flagging, deliberately not fixed here** (a real sourcing
  decision, not a wiring gap): this tool only calls DuckDuckGo's Instant
  Answer API, not real web search — for most real-world queries
  `RelatedTopics` comes back empty, so it silently returns `status: ok,
  results: []` rather than surfacing that nothing useful was found.
  `test_no_related_topics_is_still_a_status_ok_empty_list` pins that
  down as a regression guard on current behavior, not an endorsement of
  it.
- 30 new tests total across the four files. Confirmed zero regressions:
  full `vinu-agent` suite otherwise unaffected (same pre-existing 16
  failures/2 errors documented throughout this file, confirmed present
  before this change too).
- **What this leaves open**: 9 files from finding #2's original list
  remain untouched (`trade_plan_tool.py` — highest remaining value, it
  directly authors trade plans, but 1330 lines/~26 methods, only
  partially covered by two existing narrower test files; `session_search_tool.py`,
  `load_skill_tool.py`, `plan_workflow_tool.py`, `compact_tool.py`,
  `complete_step_tool.py`, `angle_clusters.py` — all lower-value
  introspection/bookkeeping, per a ranked review done before this pass).
  Finding #4 (no per-turn caching) also remains untouched.

## 12. vinu-research inefficiency audit (2026-09-25) — verified, not yet acted on

A real-code audit of `vinu-research` (excluding the already-known #3
sweep-verdict-discard issue above, which this audit was told to skip):

1. **Three incompatible ad-hoc file-storage implementations coexist with
   the proper `SQLiteBackend` pattern.** `hypothesis_registry.py:31-135`
   does it carefully (atomic tmp+`os.replace` write, exclusive-create
   lockfile with staleness detection). `judgment_store.py:39-57` is
   append-only JSONL with **no lock at all**, despite being written from
   concurrent research loops. `trade_score_calibration.py:205-216`
   writes state with a **plain, non-atomic** `path.write_text()` — a
   crash mid-write corrupts the live trade-score-threshold state.
   Meanwhile `storage/market_regime_history.py`,
   `storage/signal_evidence_store.py`, `storage/strategy_store.py` all
   already use `SQLiteBackend` — `signal_evidence_store.py`'s own
   docstring even calls these "the same kind of evidence-recording
   concern," but the other three were never migrated. Fix, smallest
   first: make `trade_score_calibration._write_state` atomic (same
   tmp+replace trick `hypothesis_registry.py` already uses); full fix:
   migrate all three onto `SQLiteBackend`.
2. **Dead code**: `comparison.py:99`'s `diverse_top_n()` (the "don't pick
   3 near-identical top candidates" rule) has zero call sites anywhere —
   `loop.py:1406,1440` calls `rank_candidates()` directly and skips
   diversity entirely. Either wire it into the top-N selection or remove
   it.
3. **`pbo.py`'s overfitting-detection math has no direct unit tests** —
   the degenerate-input fallback (line 88-97), embargo-period
   boundary-dropping logic (131-142), and Monte-Carlo sampling branch
   (107-108) are unverified. This feeds directly into the promotion
   gate's PBO threshold check, so a bug in the untested branches could
   quietly let an overfit strategy get promoted.
4. **Adjacent to the known #3 issue, not a new one**: `walk_forward.py`'s
   `run_walk_forward()` (called from `sweep_grid.py:255`) builds a full
   stability/parameter-agreement result that only exists nested inside
   the same `SweepGridResult` object #3 already flagged as discarded — so
   whatever fixes #3 needs to persist the walk-forward result too, not
   treat it as separate.

**Checked and found genuinely fine**: `market_regime_analogue.py`
already has a correct per-day cache plus durable persistence;
`loop.py` already caches `get_angle_context`/`get_feature_snapshot` once
per run (per its own comment); `promotion.py`'s `meets_promotion_bar`
doesn't duplicate `comparison.py`/`pbo.py`'s scoring, it just reads their
pre-computed fields; `maturity_assessor.py`'s apparent duplicate of
vinu-reflection's copy is deliberate and documented (avoids a circular
package dependency).

**Nothing in this item has been acted on** — recorded per instruction,
no code changed.

**UPDATE (2026-09-26)**: **finding #1's "smallest first" fix is now
built and tested** — `trade_score_calibration._write_state`'s
non-atomic write, exactly the fix this finding's own text specified.

- `trade_score_calibration.py`'s `_write_state` used a plain
  `path.write_text()` directly against the live state file — a crash
  mid-write (process kill, OOM, disk full) would corrupt it. Replaced
  with the exact tmp+`os.replace` trick `hypothesis_registry.py`'s own
  `_write` already uses (copied, not reinvented): write to a private
  temp file in the same directory, `fsync`, then one atomic
  `os.replace` — a crash mid-write now only ever leaves an orphaned
  `.tmp` file, never a truncated/corrupt live state file.
- 4 new tests in `tests/test_trade_score_calibration.py`
  (`TestWriteStateIsAtomic`): a normal round-trip, no leftover `.tmp`
  file after success, parent-directory creation, and — the actual
  property this fix buys — a `json.dump` failure mid-write (mocked)
  leaves the previously-committed state file completely untouched
  instead of corrupted.
- Confirmed zero regressions: `tests/test_trade_score_calibration.py`
  24 passed (up from 20, exactly +4). Full suite: 995 passed, 1 skipped,
  1 unrelated failure (`test_sqlite_backend.py::TestThreadSafety::
  test_concurrent_writes`) — confirmed pre-existing and flaky by
  re-running it in isolation 3 times (failed twice, passed once, a
  `sqlite3.OperationalError: database is locked` timing race in a file
  this change never touched), not a regression from this fix.
- **What this item leaves open**: finding #1's own "full fix" (migrating
  `judgment_store.py` onto `SQLiteBackend`, the same base
  `market_regime_history.py`/`signal_evidence_store.py`/`strategy_store.py`
  already use) is a bigger migration, not attempted here. Findings #2
  (dead `diverse_top_n()`), #3 (`pbo.py`'s untested overfitting-detection
  math, feeding the promotion gate), and #4 (the walk-forward result
  nested in the same discarded `SweepGridResult` as the already-known
  #3/item-#3 issue) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #1's "full fix" is
now built and tested** — `judgment_store.py` migrated onto
`SQLiteBackend`, closing the "no lock at all" gap this finding names.

- Confirmed before touching anything: `JudgmentStore`/`JudgmentRecord`
  have **zero real callers anywhere in the codebase** (only this
  module's own test file and one docstring mention elsewhere reference
  them) — the concurrency risk this finding names is currently dormant,
  not actively exploited, but the fix is exactly the same either way and
  matters the moment something does start calling `record()`.
- The old `_persist()` ran its raw JSONL file append *outside* the
  module's own `threading.Lock()`, which only ever protected the
  in-memory list, not the actual write — replaced entirely with
  `SQLiteBackend`'s WAL-mode, thread-local connections; there's no
  separate in-memory copy to keep in sync anymore, so `load()` is now a
  genuine no-op (reads are always live off the real connection), kept
  only so an existing caller of the old API doesn't break.
  `JudgmentRecord`'s own public shape is completely unchanged.
- `path=None` (the ephemeral, no-disk mode 5 of 6 existing tests already
  relied on) now maps to SQLite's own `:memory:` special path rather
  than a second, hand-rolled in-memory mechanism — one real mechanism,
  not two. Documented, not silently glossed over: a `path=None` store
  shared across multiple threads would see one independent in-memory
  database per thread (`SQLiteBackend`'s own thread-local connection
  model, same as every other subclass built on it) — not a new
  limitation this migration introduces, and nothing currently constructs
  a `path=None` store and shares it across threads (there are, again,
  zero real callers at all).
- **A flaky test caught and fixed before it could land**: a first draft
  tested concurrent writers with 20 real threads hammering brand-new
  connections to one fresh file simultaneously, and hit
  `sqlite3.OperationalError: database is locked` intermittently — traced
  to the exact same pre-existing, already-documented
  `SQLiteBackend`-level connection-setup race this session's own item
  #12 update already flagged for `test_sqlite_backend.py`'s own
  `test_concurrent_writes`. Rewritten as a deterministic test (two
  separate `JudgmentStore` instances writing sequentially to the same
  file, still the real "multiple concurrent loops" shape this finding
  names) instead of re-litigating a known base-class limitation in every
  subclass's own suite.
- 2 new tests (one existing test rewritten, not just added, to use a
  real `.db` path instead of the old `.jsonl` naming, since the format
  genuinely changed): confirms a second store instance sees committed
  writes immediately with no `load()` call needed at all (the real
  property this migration buys — the old JSONL mode required an
  explicit reload to see another process's writes), and the sequential-
  writers-to-one-file case above. Confirmed zero regressions:
  `tests/test_judgment_store.py` 8 passed (up from 6, +2), full
  `vinu-research` suite 1029 passed, 1 skipped (up from 1027, +2),
  re-run clean with no flakiness this time.
- **What this item leaves open now**: findings #2-4 (dead
  `diverse_top_n()`, `pbo.py`'s untested math, the walk-forward
  same-discard issue as item #3) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #3 fixed** — `pbo.py`'s
CSCV math now has direct unit tests; **finding #2 investigated, left
open, but for a concrete reason**, not just unattempted.

- Checked finding #2's fix options before touching anything:
  `diverse_top_n()` exists to pick a diversity-aware top-N from a
  *ranked list of several candidates* (its own docstring: "never 3
  crossover variants"), but `loop.py`'s only two call sites
  (iteration-1 generation and iteration-2+ refinement) each call
  `rank_candidates()` then immediately take `ranked[0]` — the loop never
  selects a top-N at all, it commits to exactly one best candidate per
  iteration. Wiring `diverse_top_n()` in isn't a connect-the-dots fix
  the way item #16 finding #1 or the `param_diff_from_winner` wiring
  were — it would require changing the loop's own generation strategy
  (try N candidates per iteration and backtest more than one), a real
  design decision about LLM-call budget and iteration cost, not a
  wiring gap. Left open rather than invented. Removing the dead code
  outright was also considered and rejected: it's a real, already-tested
  building block for whenever that design decision does get made, not
  pure cruft.
- `pbo.py`'s `probability_of_backtest_overfitting()` had zero direct
  tests — only indirect coverage via `test_sweep_grid.py` (`0.0 <= pbo <=
  1.0` and nothing else) despite feeding directly into
  `sweep_grid.py`'s `pbo_severe` promotion-gate check. New
  `tests/test_pbo.py`, 14 tests: the degenerate-input fallback (exact
  dict match, plus confirming the `T == n_splits*2` boundary does NOT
  fall back), a dominant-strategy case that must score exactly
  `pbo=0.0` (not just "low"), a systematically-reversing pair
  constructed to score meaningfully above the 0.5 coin-flip baseline,
  the embargo boundary-dropping logic (a real differential proven with a
  boundary-localized leakage spike — `embargo_periods=1` must produce a
  different `logit_mean` than `0`, not just accept the parameter), the
  `VINU_PBO_EMBARGO_PERIODS` env-var fallback (including its malformed-
  value branch and that an explicit param isn't overridden by it), the
  Monte-Carlo `n_combinations` sampling branch (both capped and
  larger-than-available), the `metric="mean"` branch, and `_logit()`'s
  own clamping at `p=0`/`p=1` (finite, not `inf`). Confirmed zero
  regressions: full `vinu-research` suite, 1042 passed (up from 1029,
  +13 net — 14 new tests, and the one pre-existing flaky
  `test_sqlite_backend.py::TestThreadSafety::test_concurrent_writes`
  failed on this run, already documented as a known base-class timing
  race unrelated to this change).
- **What this item leaves open now**: finding #2 (documented above, a
  real design decision) and finding #4 (walk-forward same-discard issue
  as item #3) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #4 fixed, together
with item #3 itself** — see item #3's own dated update above for the
full fix (`sweep_store.py`'s `SweepGridStore`). The walk-forward result
nested in the same `SweepGridResult` this finding named is persisted on
the same `sweep_runs` header row (`walk_forward_json`), not as a
separate mechanism, exactly as this finding's own "whatever fixes #3
needs to persist the walk-forward result too" framing asked for.
Findings #1, #3, and #4 are now all fixed — only finding #2 (the
`diverse_top_n()` design decision, deliberately left open above)
remains.

**UPDATE (2026-09-27)**: **finding #2 built and tested** — the design
decision itself explicitly authorized by the user (added backtest cost
per iteration approved; LLM-call cost is unaffected, since
`llm_candidates` candidates were already drafted in one generation call
either way).

- New `StrategyResearchLoop._backtest_and_rank_candidates()`: where
  `_default_quant_coder` used to rank the drafted candidates once, purely
  on `rank_candidates`'s pre-backtest complexity-penalty heuristic, and
  discard `llm_candidates - 1` of them on that guess alone. Now selects a
  diverse subset via the previously-dead `diverse_top_n()`, backtests
  each for real (`self._run_backtest`, the same call `run()`'s own outer
  loop already makes), and re-ranks by actual performance — `rank_candidates`'
  own `backtest_results` param (present in its signature from the start,
  see this file's earlier note on it) had simply never been called with
  real data anywhere until now.
- **A per-candidate failure doesn't abort the whole selection**: a
  candidate whose generated code crashes or produces no valid weights is
  scored as "unbacktested" (`rank_candidates`' own already-existing
  `None`-handling) rather than killing the round — only re-raises if
  *every* diverse candidate fails this way, which points at the
  environment being down rather than any one draft being bad.
- Both the iteration-1 generate path and the iteration-2+ refine path now
  go through this, not just one of them.
- 4 new tests in `test_loop.py` (`TestBacktestAndRankCandidates`):
  real backtest performance overriding the pre-backtest heuristic
  (proven with a case engineered so the two disagree, not just "a
  test passes"), one candidate's backtest raising doesn't abort the
  others, every candidate failing re-raises instead of silently picking
  one, and the generation-candidate store (item #16 finding #2) still
  records the post-backtest scores correctly. 8 existing tests across
  `TestDefaultQuantCoderRefinement`/`TestRecordGenerationRound`/
  `TestHypothesisEvidenceInStory` needed a `_run_backtest` mock added
  (they previously never triggered a real backtest during candidate
  generation at all, since none existed) — retrofitted, not silently
  left flaky. Confirmed zero regressions: full `vinu-research` suite,
  1101 passed, 1 skipped (up from 1097, same pre-existing flaky
  `test_concurrent_writes`).
- **This item is now fully closed** — all 4 findings fixed.

## 13. vinu-simulator inefficiency audit (2026-09-25) — includes a real security gap, not yet acted on

A real-code audit of `vinu-simulator`. Item 3 below is a genuine security
gap, not just an efficiency nit — flagged first on purpose:

1. **A real sandbox-escape gap in `engine/ast_guard.py:6-22`**, exercised
   via `service.py:301-304,361`'s real `exec(code, namespace)` of
   user/LLM-supplied strategy code. `validate_strategy_code` blocklists
   dangerous *imports* (`os`, `subprocess`, ...) and *calls* (`eval`,
   `exec`, `open`, `.system`, `.popen`, ...) but only inspects
   `ast.Call` nodes — it never checks `ast.Attribute` access. Classic
   Python sandbox escapes that reach `os`/`subprocess` without ever
   writing the word `import` — e.g.
   `().__class__.__base__.__subclasses__()` or
   `(lambda: None).__globals__['__builtins__']['eval']` — pass through
   completely unblocked. Also missing from `_FORBIDDEN_CALLS`: `input`,
   `exit`, `quit`, `breakpoint`, `vars`, `globals`. Since this gates real
   `exec()` of code that may originate from an LLM-generated strategy,
   this is an exploitable gap, not an overly-cautious restriction to
   loosen — the opposite direction from most items in this file.
2. **Redundant storage**: `storage/results.py:81-86` writes a `meta.json`
   per run duplicating `strategy_name`/`run_id`/`timestamp` fields
   already in `storage/meta.py`'s SQL row; `load_meta()` is the only
   reader. Fix: drop it, read from `MetaStorage.get_run()` instead.
3. **Symbol-filtered queries decode the whole table**: `storage/meta.py`'s
   `list_runs(symbol=...)` (lines 205-229) has no SQL `WHERE` on symbol —
   it loads and JSON-decodes every row, then filters in Python; the
   `symbols` column has no index and is stored as an unindexed JSON blob.
   Gets slower as sweep-run volume grows. Fix: a normalized
   `run_symbols(run_id, symbol)` join table.
4. **No caching on price/feature client fetches**
   (`clients/price_client.py`, `clients/features_client.py`) — same
   pattern as the `vinu-agent` tools finding (item 11.4): identical OHLCV
   data gets re-fetched from the network on every run, even across a
   sweep hitting the same symbol/date range repeatedly. Retry/backoff
   itself (`clients/base.py`) is consistent across all three clients — no
   inconsistency there, just no caching layer at all.
5. **Dead code**: `server/schemas.py:57` (`MetricRow`) and `:149`
   (`SimulateDryRunResponse`) — both defined, neither referenced anywhere
   else in the tree.
6. **Missing test coverage**: `storage/results.py`, `clients/base.py`
   (retry/backoff loop), `clients/price_client.py` (thread-pool fan-out,
   missing-symbol error path), and notably `service.py` itself (701
   lines, the main orchestration/caching/hashing logic) has no dedicated
   test file — only indirectly touched via one sizing-focused test.

**Checked and found genuinely fine**: `engine/regime.py`'s
point-in-time-safe z-score fix is intact and directly tested
(`test_attribution.py::test_classify_regime_short_series_matches_long_prefix`).
`engine/sizing.py` correctly delegates Kelly math to
`vinu_infra.risk_math.kelly_fraction`, with `VolTargetSizer`'s
non-delegation to `vol_target_scale` being a documented, intentional
semantic difference, not hand-rolled duplication. `engine/costs.py` has
no equivalent elsewhere to duplicate. Minor/low-priority, not worth its
own item: `regime.py:24`'s `bfill()` fills the series' very first bar
using the next bar's value — a one-bar look-ahead limited to that single
edge case, not affecting the documented fix.

**Nothing in this item has been acted on** — recorded per instruction,
no code changed.

**UPDATE (2026-09-26)**: **finding #1, the real sandbox-escape gap, is
now fixed and tested** -- the genuine security issue in this item, fixed
first and on its own, ahead of the efficiency findings below it.

- `engine/ast_guard.py`: the `ast.walk` loop only ever branched on
  `ast.Import`/`ast.ImportFrom`/`ast.Call` -- an `ast.Attribute` node was
  only ever inspected when it happened to be a `Call`'s `.func`, and only
  against `_FORBIDDEN_ATTR_CALLS`'s short list (`system`, `popen`, `run`,
  ...), which never included reflection attributes like
  `__subclasses__`. Both techniques the finding named are `ast.Attribute`
  nodes that either aren't calls at all (`.__globals__` is subscripted,
  never called) or whose dangerous *name* (`__subclasses__`) was simply
  absent from the old blocklist. Fixed by adding a new
  `_FORBIDDEN_ATTRS` set (`__class__`, `__base__`, `__mro__`,
  `__subclasses__`, `__globals__`, `__builtins__`, `__dict__`,
  `__getattribute__`, `__reduce__`, and similar reflection/introspection
  dunders) and a new top-level `elif isinstance(node, ast.Attribute)`
  branch that checks every attribute-access node in the tree against it
  -- independent of whether it's part of a `Call`, so both
  `().__class__.__base__.__subclasses__()` (attribute chain ending in a
  call) and `(lambda: None).__globals__['__builtins__']['eval']`
  (attribute access that's subscripted, never called) are caught the
  same way. Also closed the other gap this finding named in passing:
  `_FORBIDDEN_CALLS` gained `input`, `exit`, `quit`, `breakpoint`,
  `vars`, `globals`.
- Confirmed this is a real, not theoretical, gap before calling it done:
  `service.py`'s `exec(code, namespace)` runs with a plain `dict`, which
  Python auto-populates with the real `__builtins__` (this is standard
  `exec()` behavior when the globals dict doesn't already define
  `__builtins__`) -- so `eval`/`open`/etc. are already present in the
  executed namespace regardless of what the code itself imports; the AST
  guard is the *only* thing standing between that and the techniques
  above.
- 5 new tests in `tests/test_ast_guard.py`
  (`TestSandboxEscapeGap`): both named bypass techniques confirmed now
  blocked, a bare (uncalled) dunder-attribute-access case confirmed
  blocked on its own to prove the fix isn't call-shaped, all 6 newly
  added forbidden calls confirmed blocked, and a legitimate-strategy-code
  regression guard (ordinary `data.close.rolling(20).mean()`-style
  attribute access) confirmed it still passes clean -- the fix doesn't
  just widen the blocklist into false positives on normal code.
  Confirmed zero regressions: full `vinu-simulator` suite, 176 passed
  (13 of them in `test_ast_guard.py`, up from 8).
- **What this item leaves open**: findings #2 (redundant `meta.json`
  storage), #3 (unindexed symbol-filtered queries), #4 (no caching on
  price/feature client fetches), #5 (dead code in `server/schemas.py`),
  and #6 (missing test coverage for `storage/results.py`,
  `clients/base.py`, `clients/price_client.py`, and `service.py` itself)
  are untouched -- all real, but efficiency/coverage nits, not security
  gaps, correctly lower priority than finding #1.

**UPDATE (2026-09-26, later same day)**: **finding #2 fixed, and a slice
of finding #6 (this same file's own missing test coverage) closed at the
same time.**

- Re-checked the claim before touching anything: grepped the whole
  codebase for `load_meta` -- zero real callers anywhere, not just "the
  only reader" the finding described. `meta.json` was pure write-only
  dead weight, and its own reader (`ResultStorage.load_meta()`) was
  itself fully dead code, not merely redundant with `MetaStorage.get_run()`.
  Removed both the write in `save()` and the dead `load_meta()` method
  outright (no caller existed to redirect to `MetaStorage.get_run()`,
  so there was nothing to migrate) -- confirmed
  `tests/test_run_card.py`'s own `meta.json` reference is unrelated (a
  synthetic fixture file it writes itself to test generic artifact-
  hashing, independent of whether `ResultStorage` ever produces one).
- New `tests/test_result_storage.py` -- this module had zero dedicated
  tests before (finding #6's own claim, confirmed) -- 9 tests covering
  the real save/load round-trip for equity/weights/trades, empty-trades
  and unknown-run-id fail-open behavior, `delete()`, and two direct
  regression guards for this fix: no `meta.json` file gets written, and
  `load_meta` is no longer a method on the class at all.
  Confirmed zero regressions: full `vinu-simulator` suite, 185 passed
  (up from 176, exactly +9).
- **What this item leaves open now**: finding #3 (unindexed queries),
  finding #4 (no caching), finding #5 (dead schema code), and the rest
  of finding #6 (`clients/base.py`, `clients/price_client.py`,
  `service.py` itself still untested) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #5 fixed, and the
`clients/base.py`/`clients/price_client.py` slice of finding #6 closed.**

- Confirmed before removing anything: grepped the whole tree for
  `MetricRow`/`SimulateDryRunResponse` — zero references anywhere outside
  their own definitions in `server/schemas.py`, exactly as the finding
  described. Both removed outright.
- `clients/base.py` turned out to already use a thread-local
  `httpx.Client` per calling thread (`self._local = threading.local()`),
  not a single shared instance — this file never had vinu-strategy's item
  #22 finding #7 lock-serialization problem to begin with, a real
  design difference worth confirming with a test rather than assuming.
  Also notable and now pinned down by a test: this client re-raises on
  exhausted retries and lets non-transient `httpx.HTTPError` propagate
  uncaught, rather than swallowing into `{}` the way vinu-strategy's
  `BaseClient` does — `price_client.py`'s own per-symbol `_fetch` closures
  rely on this (`except Exception: return sym, None`) to turn one
  symbol's failure into a skip rather than crashing the whole batch. New
  `tests/test_base_client.py`, 8 tests: request basics (success/retry/
  exhaustion/timeout/non-transient propagation) plus two tests directly
  on the thread-local design (four real threads each get a distinct
  client instance; `close()` only closes the calling thread's own
  client).
- New `tests/test_price_client.py`, 7 tests covering `get_ohclv`'s
  thread-pool fan-out (per-symbol success, a raising symbol dropped not
  propagated, empty/missing `data` key handled, indicator-column
  filtering) and `_fetch_price_data`'s two `ValueError` paths (all
  symbols failed, one symbol missing from the pivoted frame) plus a
  clean aligned-frames case for `get_price_and_volume`.
- Confirmed zero regressions: full `vinu-simulator` suite, 200 passed
  (up from 185, exactly +15).
- **What this item leaves open now**: finding #3 (unindexed queries),
  finding #4 (no caching), and `service.py`'s own missing test coverage
  (the rest of finding #6) remain untouched.

**UPDATE (2026-09-27)**: **finding #3 fixed** — exactly the normalized
join table this finding's own text proposed, `run_symbols(run_id,
symbol)`.

- `storage/meta.py`: new `simulation_run_symbols(run_id, symbol)` table,
  `PRIMARY KEY (run_id, symbol)`, indexed on `symbol`. `_ensure_run_symbols_table()`
  backfills it once from the existing `symbols` JSON column, gated on the
  table not existing yet — a genuine one-time cost on an old database,
  a cheap no-op check on every startup after.
- `insert_run()` now writes through to the join table (clearing a
  run_id's old rows first, since `INSERT OR REPLACE` on `simulation_runs`
  means a re-run under the same run_id can legitimately change its symbol
  list). `delete_run()`/`delete_runs()` cascade-delete the matching join
  rows, so nothing dangling accumulates.
- `list_runs(symbol=...)` now issues a real `WHERE`/`JOIN` against the
  indexed table instead of loading and JSON-decoding every row to filter
  in Python — the exact query-shape change this finding asked for.
- 8 new tests in `test_meta_validation_storage.py`: combined
  strategy+symbol filtering, re-inserting a run_id replaces (not
  accumulates) its join rows, `delete_run`/`delete_runs` clean up their
  join rows, and a dedicated migration test simulating a pre-existing
  database with populated `symbols` JSON but no join table yet, confirming
  the backfill makes it queryable. Confirmed zero regressions: full
  `vinu-simulator` suite, 205 passed (up from 200, +5).

**UPDATE (2026-09-27, later same day)**: **finding #4 fixed** — a bounded
per-instance LRU cache on both HTTP clients, same idiom
`vinu_research/loop.py`'s own `_LRUCache` already established for its
feature-snapshot cache (reimplemented locally as
`clients/_cache.py::LRUCache` rather than imported cross-service, since
neither service depends on the other's package).

- `PriceClient`/`FeaturesClient` each gained a `cache_maxsize` constructor
  param (default 256) and cache the DataFrame(s) their fetch methods
  return, keyed by the exact request shape. Safe by construction, not
  just by convention: `service.py` constructs exactly one long-lived
  instance of each per `SimulatorService`, so a cache scoped to the
  instance's own lifetime (not a new shared store, no new persistence
  decision) is exactly the "a sweep hitting the same symbol/date range
  repeatedly" case this finding named.
- **Two correctness details that mattered, not just "add a dict"**:
  (1) `get_ohclv`'s cache key sorts symbols (its return is a dict, order
  is irrelevant, so this improves the hit rate for free); `_fetch_price_data`'s
  key deliberately does **not** sort them, since its return selects
  DataFrame columns via `pivot_prices[symbols]` in the exact requested
  order — sorting that key would have let a differently-ordered request
  silently receive mis-ordered columns from a stale cache hit. (2)
  Neither key normalizes symbol case — `sym` is passed verbatim into the
  real `/candles/{sym}` request, so a case difference is a genuinely
  different request, not a cache-equivalent one; normalizing it would
  have risked conflating two different real API calls. Every cache hit
  returns `.copy()` of the stored frame(s), so a caller mutating its
  result in place can never corrupt what a later cache hit returns.
  Only successful fetches are cached — a failed/exception fetch is never
  memoized as a false "this symbol has no data" answer.
- 20 new tests: 5 in new `tests/test_client_cache.py` (the `LRUCache`
  helper itself: miss, round-trip, eviction, recency-refresh-on-get,
  clear), 9 added to `test_price_client.py` (`TestOhclvCache`/
  `TestFetchPriceDataCache` — repeated identical requests don't refetch,
  symbol-order-independence for `get_ohclv` vs. order-sensitivity for
  `_fetch_price_data` proven as two *different*, deliberate behaviors
  rather than one being an oversight, a different date range is a real
  miss, a cache hit returns an independent copy), 4 added to
  `test_features_client.py` (`TestGetIndicatorsCache` — repeated request
  dedup, kind-order independence, a failed fetch is never cached,
  independent-copy-on-hit). Confirmed zero regressions: full
  `vinu-simulator` suite, 220 passed (up from 205, +15).
- **What this item leaves open now**: `service.py`'s own missing test
  coverage (the rest of finding #6) is the only piece of this item still
  untouched.

**UPDATE (2026-09-27)**: **finding #6 fully closed** — `service.py` (701
lines, the main orchestration/caching/hashing logic) now has a dedicated
test file, the last untouched piece of this whole item.

- New `tests/test_service.py`: the OHLCV in-process cache's own TTL/
  key/eviction behavior (repeat call hits the cache, symbol-order doesn't
  defeat it, a different date range is a real miss, an expired entry
  refetches), `_compute_config_hash`'s determinism and key-order-
  independence, `_compute_benchmark_metrics` (present ticker, missing
  ticker skipped, <2 valid points skipped), every read/delete method
  (`get_result`/`get_equity`/`get_weights`/`get_trades`/`list_runs`/
  `delete_run`/`delete_runs`) through real `MetaStorage`/`ResultStorage`
  instances seeded directly (not mocked), `close()`'s three real
  delegate calls, a real end-to-end `simulate()` happy path plus its
  config-hash cache-hit path (only the client calls are faked;
  `WeightSimulator` actually runs), and `simulate_custom()`'s three
  validation paths (security-code rejection, unknown class name, wrong
  base class) — none of which had any coverage anywhere before this
  file.
- **A real, previously-undetectable bug found and fixed while writing
  these, not worked around**: `simulate()`'s own `dry_run=True` branch
  constructed `SimulationResult` missing three required (no-default)
  fields — `config`, `daily_returns`, `weights_history` — that the
  dataclass had apparently grown after this call site was last touched.
  Any real `dry_run=True` request would have crashed with a `TypeError`
  the instant it reached this line; nothing caught it because this
  branch had zero test coverage and, per this file's own grep, zero real
  callers pass `dry_run=True` today either. Fixed by constructing a real
  minimal `SimulationConfig` and using `pd.Series(dtype=float)`/
  `pd.DataFrame()` for the missing fields — checked both real consumers
  of `result.portfolio_values`/`.trades` (`api.py`, `routes_read.py`)
  first: both only ever call `len(...)` on them, which behaves
  identically for an empty list or an empty Series/DataFrame, so this is
  a pure bug fix with no observable behavior change for any existing
  caller.
- Confirmed zero regressions: full `vinu-simulator` suite, 251 passed
  (up from 220, exactly +31).
- **This item is now fully closed** — every numbered finding (#1-6) has
  either been fixed or, for #3/#4 above, fixed in this same file's own
  earlier updates.

## 14. Senior-quant recommendation: composite risk sizing, and structured (not silent) failure recording for sweeps

Asked directly: "if you were the senior quant engineer, how should the
simulator work, what do you want to see." Two concrete recommendations,
neither implemented, both refining earlier items (#4's sizing idea, #3's
sweep-verdict gap) with more specific shape.

### A. Risk sizing should compose multiple factors, not rely on one

`engine/sizing.py`'s `PositionSizer` abstract base class is
architecturally right — pluggable, one factor per class, independently
testable. The gap is that every real sizer today is single-factor:
`FixedSizer` (no adjustment), `VolTargetSizer` (trailing realized
volatility only). A real sizing decision should never be single-factor.
Four factors, each already has a real, existing building block
elsewhere in this codebase that nothing currently wires into sizing:

1. **Evidence-confidence** — size up when Track 1/Track 2's recorded
   expectancy for this exact condition is strong, down when thin or
   unproven (the `EvidenceConfidenceSizer` already sketched in item #4).
   This is the piece most directly tied to everything else in this
   folder, and the one currently missing entirely.
2. **Regime-aware** — `engine/regime.py` already classifies
   `bull`/`bear`/`high_vol`/`neutral` point-in-time-safely (see item
   #13's confirmation this fix is intact and tested), but no sizer reads
   it. A strategy that only works in low-vol regimes should shrink
   automatically as the regime shifts, not rely on the strategy author
   hard-coding that themselves.
3. **Drawdown-aware** — `vinu-portfolio/circuit_breakers.py`'s
   `PortfolioDrawdownMonitor` and `drawdown_scheduler.run_once()` exist,
   but **checked directly (2026-09-25): this is not a drop-in.**
   `run_once(monitor, agent_api_url)` is built for live polling against a
   running agent API, not a pure function callable inside a backtest
   loop. Using this in the simulator requires first extracting the pure
   threshold logic out of `PortfolioDrawdownMonitor` into something
   backtest-callable (or reimplementing the same rule in a
   backtest-friendly form) — a real, separate piece of work, not just a
   wire-up. Without it, though, a backtest's reported expectancy stays
   systematically more optimistic than live trading would actually
   produce, since live drawdown throttling would have cut exposure at
   points the backtest currently never does.
4. **Correlation-aware** — `vinu-portfolio/shock_correlation.py` **checked
   directly: this one genuinely is a drop-in** — fully computational
   (Gerber correlation, GARCH conditional variance, DCC shock
   correlation, all numpy, no live coupling), the simulator's sizer just
   never calls it. Two positions that are secretly the same underlying
   bet can both get full size in a backtest today.

**The recommended shape**: a `CompositeSizer` taking an ordered list of
these factors and multiplying them down (vol-target × evidence-confidence
× regime-adjustment × drawdown-throttle), each independently
on/off-toggleable — so a backtest can isolate which factor is actually
earning its keep, rather than one monolithic function baking all four
together permanently. Output should be **dollar expectancy, not just
Sharpe** — "if $100 went into this signal under this sizing scheme, here's
the expected P&L and its distribution" (ties back to item #4's original
ask).

### B. Sweep failures need structured verdicts, not silent removal

Extends item #3's already-identified gap (sweep rankings computed then
discarded) with two specific fields worth calling out on their own,
prompted directly by the question "if a candidate continued fine but had
worse PnL, how should that be stored instead of just removed":

- **Categorized `rejection_reason`**, not a free-text guess and not just
  a bare score — e.g. `"worse_sharpe"` vs `"failed_pbo_gate"` vs
  `"failed_walk_forward_stability"` vs `"higher_drawdown"`. These are
  categorically different kinds of failure and should be independently
  queryable later ("show me every candidate that failed the PBO gate
  specifically," not just "show me every loser").
- **`param_diff_from_winner`** — the specific parameter(s) that differed
  from the winning candidate (e.g. "identical to the winner except ADX
  period was 20 instead of 14"). This is the single most valuable field
  of the two: it's the difference between having a pile of losing runs
  and having a direct, readable answer to "what specifically cost this
  candidate the win" — the actual teaching material a future
  strategy-writer needs, not just a worse number.

Both fields extend, not replace, item #3's proposed
`sweep_id`/`run_id`/`rank`/`score` grouping table — add
`rejection_reason` and `param_diff_from_winner` columns to that same
table when it gets built.

**Checked directly (2026-09-25): this is smaller work than it first
looked.** `vinu-research/sweep_grid.py` already computes
`GridPointOutcome` (`params`, `succeeded`, `error`) and
`RankedSweepCandidate` (`score`, `risk_score`, `complexity_score`,
`params`) for *every* candidate in a sweep, not just the winner — this is
exactly the raw material both new fields need, already sitting in memory
at the point `SweepGridResult` gets built (per item #3). `error` only
covers candidates that crashed, though — a `rejection_reason` category
for candidates that ran fine but simply scored worse is still a genuine
gap. `param_diff_from_winner` needs no new data collection at all: every
candidate's `params` dict already exists, so it's a diff function
against the top-ranked candidate's `params`, applied at the same persist
point item #3 already identifies.

**Nothing in this item has been implemented** — recorded as design
recommendation only, per instruction.

**UPDATE (2026-09-26)**: **part B's `param_diff_from_winner` field is now
built and tested** — exactly the piece this item's own "checked directly"
note said needed no new data collection, so it was the one buildable
piece without first inventing item #3's still-undesigned persistence
table.

- New `vinu_research/sweep_grid.py::param_diff_from_winner(candidate_params,
  winner_params)` — a pure diff function, sparse (`{}` for identical
  params), comparing a key present on only one side against `None` on the
  other rather than silently skipping it (so a candidate that dropped or
  added a param entirely still shows up).
- **Wired through to where a caller can actually see it, not left
  stranded**: `server/routes_sweep.py`'s `_serialize_grid` — the function
  `POST /sweep/grid`'s real HTTP response is built from — now computes
  each ranked candidate's diff against `result.ranked[0]` (already
  best-first, `comparison.py`'s `rank_candidates` sorts by score
  descending) and adds it as `param_diff_from_winner` on every entry in
  the response's `ranked` list, including the winner itself (against its
  own params, always empty, so a caller doesn't need to special-case rank
  0). Fails open to `{}` when `result.ranked` is empty (every grid point
  crashed) rather than an `IndexError`.
- 7 new tests in `tests/test_sweep_grid.py`: `TestParamDiffFromWinner`
  (5, the pure function — no diff, a real diff reported both sides, a
  key present on only one side either direction, both-empty) and
  `TestSerializeGridIncludesParamDiff` (2, through the real
  `run_sweep_grid()` → `_serialize_grid()` chain — confirms the winner's
  own diff is empty and the losing candidate's diff correctly isolates
  the one param that actually differed, plus the empty-`ranked`
  fail-open case).
- Confirmed zero regressions: full `vinu-research` suite, 1003 passed, 1
  skipped (up from 995 -- the +8 includes 7 new tests plus
  `test_sqlite_backend.py`'s already-known flaky
  `test_concurrent_writes` happening to pass on this run rather than
  fail, confirmed flaky/unrelated in item #12's own update above).
- **What this item leaves open**: part A (the `CompositeSizer` combining
  evidence-confidence/regime/drawdown/correlation factors) is untouched —
  a real, larger implementation project, not a well-scoped single fix.
  Part B's `rejection_reason` categorization is also untouched: unlike
  `param_diff_from_winner`, it genuinely needs new data collection this
  item's own "checked directly" note admits isn't sitting in memory
  anywhere yet (per-candidate PBO/walk-forward-stability breakdown,
  currently only aggregate fields on `SweepGridResult`) — a real,
  separate piece of design work, not invented here. Item #3's own
  persistence table (the place these fields are meant to eventually live
  as durable columns, per this item's own text) also remains unbuilt.

**UPDATE (2026-09-27)**: **part A's `CompositeSizer` built, two of the
four named factors** — vol-target and correlation-aware. Explicitly
scoped down, not silently declared "done": evidence-confidence and
drawdown-aware sizing remain separate, real design decisions (this
finding's own text already flagged drawdown-aware as needing real
extraction work out of `PortfolioDrawdownMonitor`, and evidence-
confidence has no sketch anywhere in the codebase, confirmed by a fresh
grep — this finding's own "already sketched in item #4" claim doesn't
hold up; corrected here, not silently carried forward).

- New `vinu_simulator/engine/sizing.py::CompositeSizer`: multiplies a
  vol-target factor (existing `VolTargetSizer` math, extracted into a
  shared `_vol_target_scale_factor()` helper so both classes use the
  identical formula, not two copies) with a correlation-aware shrinkage
  factor, applied to the strategy's own weight vector exactly like every
  other sizer here — direction/which-symbols still only ever comes from
  the strategy.
- **Correlation-awareness reuses the exact math this finding's own
  "checked directly: this one genuinely is a drop-in" note pointed at**
  (`vinu-portfolio/shock_correlation.py`'s DCC-GARCH/Gerber shock
  correlation) — relocated to `vinu_tools/compute/risk/shock_correlation.py`
  first (a shared home both services can import from) rather than a
  second, independently-derived correlation model; `vinu-portfolio`'s own
  copy is now a thin re-export, its existing 14 tests unchanged and still
  passing.
- **A real performance decision, not just "call the function"**:
  refitting a GARCH model per symbol on every single rebalance day would
  make a backtest using this sizer prohibitively slow. The correlation
  factor is cached and only recomputed every N rows of new return
  history (default 20), not every step — bounded, documented, and
  covered by a dedicated cache-hit test.
- `PositionSizer.size()`'s abstract signature gained an optional
  `symbol_returns` kwarg (every existing sizer accepts and ignores it,
  so the engine's one call site can pass it unconditionally without an
  `isinstance` check); `WeightSimulator.run()` builds the per-symbol
  return history once before the loop and only for `CompositeSizer`
  specifically (an `isinstance` guard), so every other sizer pays
  nothing extra.
- 24 new tests: 14 in `vinu-tools/tests/test_risk_shock_correlation.py`
  (the relocated module's own canonical, directly-tested home — the
  same 14 cases `vinu-portfolio`'s test file already had, ported rather
  than trusting the re-export blindly), 7 in `test_sizing.py`
  (`TestCompositeSizer` — no-symbol-returns falls back to vol-target
  only, a single-symbol frame is safely ignored, insufficient
  correlation history leaves only the vol factor applied, highly
  correlated symbols shrink more than uncorrelated ones — the actual
  property this factor buys, proven with an engineered case rather than
  trusted — the shrink cap is respected, the cache serves stale data
  within the recompute interval, direction is never flipped), 3 in
  `test_simulator.py` (`TestCompositeSizerWiredThroughTheRealEngine` — a
  real end-to-end run, the sizer actually receives a real multi-column
  frame from the engine at some point in the run, and a non-composite
  sizer never pays for building it at all). Confirmed zero regressions:
  `vinu-simulator` 262 passed (up from 251, +11), `vinu-tools` 175
  passed (up from 161, +14), `vinu-portfolio` 251 passed unchanged (the
  relocated-module re-export left every existing caller untouched).
- **What this leaves open now**: evidence-confidence and drawdown-aware
  sizing factors, and part B's `rejection_reason` categorization, remain
  unbuilt — each a real, separate piece of work.

## 15. No incremental/rolling backfill — the gap between "last analyzed date" and "today" is never automatically detected or filled

**The problem, stated explicitly, checked directly against the real code
(2026-09-25)**: every angle run is tagged with a fixed date range
(`analysis_from`/`analysis_until`), and `has_existing_run()`
(`vinu-initial-analysis/storage/meta.py:163-193`) does an **exact-match**
check on that range — it can only answer "has this exact window already
been run," never "is there a gap between what's covered and today."
Nothing in `runner.py` (the caller of `has_existing_run()`) computes
"last covered end date → today" as the next range to request — whatever
`from_ts`/`to_ts` gets passed in is entirely up to the caller, with no
visible logic anywhere that derives it from what's already been run.

**Concretely, the scenario that surfaced this**: a ticker analyzed
through August, checked again in October — nothing detects the
August-to-October gap and automatically requests it. The coverage view
(`ticker_coverage.py`) makes this invisible rather than visible: it
reports `start_date`/`end_date` as just the min/max of whatever's been
run, with **no comparison to today's date anywhere in that file** (grepped
for `stale`/`today`/`datetime.now`/`utcnow`: zero hits). A ticker last
analyzed in August looks identical, in the coverage table, to one
analyzed yesterday — there's no staleness flag.

**Why this matters beyond just tidiness**: this is the exact seam where
historical backfill needs to hand off to live/present-moment recording
(item #5) — at some point, "the backfill's end date" needs to either (a)
trigger another backfill run extending forward to today, or (b) hand off
to the live detector picking up from today forward. Right now nothing
decides where that boundary is, nothing triggers the fill automatically,
and nothing even surfaces that a gap exists.

**Open, not designed**: whether the fix is (a) a staleness flag added to
the coverage view first (visibility before automation), (b) the
screener/orchestrator computing `last_end_date → today` as the next
requested range automatically, or (c) both — not decided. This is
closely related to but distinct from item #5: #5 is about recording
present-moment computation as it happens; this item is about detecting
and filling the historical gap that accumulates *before* present-moment
recording would even take over.

**Concrete field for option (a)**: add `days_stale: int` (computed at
read time, `today - end_date`, never stored — same "derived fresh, never
cached" rule as `ticker_coverage.py` already follows elsewhere in that
same file) to `ticker_coverage.py`'s per-angle coverage dict. This alone
makes the gap *visible* without yet deciding whether to automate filling
it — a deliberately small, low-risk first step ahead of option (b)'s
larger orchestrator change.

**UPDATE (2026-09-26)**: **option (a) is now built and tested** — exactly
the field this item's own text specified, and exactly the "small,
low-risk first step" it was framed as (option (b), the orchestrator
change that would actually fill a detected gap, is a separate, larger
decision not made here).

- `storage/ticker_coverage.py`'s new `_days_stale(analysis_until)`
  computes `(today - analysis_until).days` fresh on every call — never
  stored, matching this module's own already-stated rule that everything
  it reports is a read-side pivot, not a second source of truth. Added
  as `"days_stale"` on each angle's own dict entry in
  `build_ticker_coverage()`'s `angles` mapping (only where real data
  exists — an angle still `PENDING`/`NOT_REQUIRED` stays the plain
  string it already was, since there's no `analysis_until` to measure
  staleness from). `None` on any missing or unparseable
  `analysis_until`, rather than a misleading `0`.
- **Already reaches a real caller with zero extra wiring**:
  `server/routes_read.py`'s ticker-coverage route returns
  `build_ticker_coverage()`'s dict directly as the HTTP response body —
  `days_stale` is visible to any API caller the moment this function
  computes it, nothing else needed.
- 5 new tests in `tests/test_ticker_coverage.py`
  (`TestDaysStale`): a same-day run reports `0`, a run from exactly 60
  days ago reports `60`, an angle that's never run stays a plain string
  (not a dict with a meaningless `days_stale`), the helper fails open to
  `None` on missing/unparseable input, and a naive (no-tzinfo) ISO string
  is treated as UTC rather than raising. Confirmed zero regressions:
  `tests/test_ticker_coverage.py` 13 passed (up from 8, +5),
  `tests/test_ticker_coverage_route.py` 3 passed unchanged, and the full
  `vinu-initial-analysis` suite (46 failed, 362 passed, 2 skipped, 24
  errors) -- the 46 failures/24 errors are the same pre-existing
  ML-dependency collection errors confirmed unrelated earlier in this
  file (item #20 finding #7's own update), identical count to that
  earlier baseline; passed went 357 -> 362, exactly the +5 new tests.
- **What this item leaves open**: option (b) itself (the screener/
  orchestrator automatically computing and requesting `last_end_date →
  today` as the next backfill range) is a real, separate implementation
  decision, not attempted here — this pass only makes the gap visible,
  as designed.

## 16. Real end-to-end pipeline trace (2026-09-25), and five senior-quant autonomy gaps found by tracing it

**Checked directly against the real code.** The screener→pre-analysis→
strategy-generation→research→simulator pipeline is genuinely working
end-to-end, not stubs: `vinu-agent/cli.py`'s `planner-worker` loop →
`PlannerTriage.check()` (K-cap gate, default 3 in-flight candidates per
ticker, `thesis_intake_gate.py:36`) → `LlmStrategyGenerator.generate()`
(`vinu_research/llm_generator.py:351-385`, 3 concurrent LLM drafts,
config `VINU_RESEARCH_LLM_CANDIDATES`) fed real `angle_context`/
`feature_snapshot` (`loop.py:246-261`) → `HypothesisRegistry.query_by_symbol`
fuzzy-match/create (`loop.py:274-300`) → best-ranked candidate → HTTP
backtest via `ResearchTools.run_backtest` → `vinu-simulator` →
evidence written back to the matched hypothesis.

**One correction to how this was described earlier**: the ticker list is
**not** read live from `vinu-screener` each cycle. It comes from a
locally-persisted `TickerSummaryStore`, bootstrapped from a static
`VINU_AGENT_WATCHLIST_SEED_TICKERS` env var — `vinu-screener` is wired in
only as an optional, best-effort contributor to that seed list, not the
loop's actual ticker source.

Five gaps found by tracing this, none acted on:

1. **The two evidence systems still don't talk to each other — the
   biggest one.** The research loop already writes `Evidence` into
   `HypothesisRegistry` from backtest results (this part of items #1/#7
   already works, just for a different evidence stream than Track 1's).
   But Track 1's `signal_evidence` angle's historical must-condition
   trigger/outcome data never feeds into strategy generation — the LLM
   drafting a new candidate sees today's indicator snapshot but never
   "here's what happened historically the last N times this exact
   must-condition fired." Concretely: `llm_generator.py`'s
   `_build_generation_prompt`/`_build_refinement_prompt` should be fed
   `get_signal_evidence`-style results, not just raw indicator values.
   This sharpens item #1's fix location precisely.
2. **Generation-time candidate loss — a new, earlier discard point than
   item #14's sweep-candidate loss.** 3 candidates get drafted per
   generation call; 2 are discarded immediately based on a **heuristic
   complexity-penalty score with no backtest behind it yet** — never
   recorded, never backtested, and the ranking itself is never validated
   against real outcomes. Same "record failures, not just winners"
   principle as Track 2 and item #14, one step earlier in the pipeline.
3. **A unified "candidate graveyard" is needed, not three separate,
   disconnected rejection mechanisms.** An idea can currently die at
   generation-time (point 2, heuristic rank), sweep-time (item #14, real
   backtest), or hypothesis-level (item #7's `reject_with_reason`).
   Structurally these are the same fact — "this was tried, here's why it
   didn't survive" — but nothing unifies them into one queryable place,
   so the system can't ask "has something like this already failed, and
   why" across all three death points at once.
4. **The hypothesis dedup check is fragile.** `_match_score`
   (`loop.py:53-59`) is a fuzzy text-overlap on `strategy_type` at a 0.5
   threshold. Two conceptually identical strategies phrased differently
   could both get generated and tested (wasted budget); two different
   strategies phrased similarly could get merged into one hypothesis's
   evidence trail (corrupted attribution). Item #1's structured
   `must_conditions`/`indicators_used` schema would dedup far more
   reliably than string similarity once it exists.
5. **Ticker discovery needs to be a real loop, not a seed-and-forget.**
   For genuine autonomy, the loop should read `vinu-screener`'s live
   ranked output as its ticker source each cycle, with the current static
   watchlist becoming the fallback/override rather than the primary path.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Priority not yet decided by the user.

**UPDATE (2026-09-26)**: **finding #1 fully closed** — first recorded as
half-closed (item #1's wiring alone made the evidence reachable, not
read), then finished the same day on tracing the actual prompt-building
path one level further, per this file's own procedure of tracing to the
real consumer rather than stopping once something is technically
reachable.

- `loop.py`'s `_default_quant_coder` turned out to **already** pull
  `hyp.evidence[-3:]` into `story["memory_context"]`, which
  `_build_generation_prompt`/`_build_refinement_prompt` already render
  into the real prompt — this piece of wiring pre-dated this finding
  entirely and the audit hadn't noticed. The actual, narrower gap: the
  formatting line showed a bare `metric=value → conclusion` triple,
  dropping `reasoning` — for item #1's new signal-evidence entries,
  `reasoning` (e.g. "12 historical trigger(s) of 'sma5_cross_sma50', 58%
  positive, last fired 3 day(s) ago") is the *only* informative part;
  the bare metric/value pair (`avg_return_at_horizon=0.03 → supports`)
  is nearly meaningless on its own.
- Fixed by branching on the same `metric_kind` field item #1 already
  added: `metric_kind == "signal_evidence"` entries render their full
  `reasoning`; everything else (existing Sharpe-based evidence, whose
  own `reasoning` is a full LLM critique paragraph, not a short summary)
  keeps the original terse format unchanged, so this doesn't bloat the
  prompt for the existing common case.
- 3 new tests in `test_loop.py` (`TestHypothesisEvidenceInStory`,
  through the real `_default_quant_coder` → `refine()` call chain, not
  the prompt-builder in isolation): a signal-evidence entry's full
  reasoning appears in the built story, a Sharpe entry keeps its terse
  form and its long critique text does *not* leak into the prompt, and a
  mixed-kind hypothesis formats each entry correctly by its own kind.
  Confirmed zero regressions: full `vinu-research` suite, 1022 passed, 1
  skipped (up from 1018, +3, consistent with item #1's own count once
  the previously-flaky `test_concurrent_writes` is accounted for).
- **What this item leaves open**: findings #2-5 (generation-time
  candidate loss with no recorded verdict, no unified rejection ledger
  across all three death points, the fragile `_match_score` dedup this
  same file's hypothesis-matching code still uses, and seed-and-forget
  ticker discovery) are all untouched — each is a real design decision,
  not a wiring gap.

**UPDATE (2026-09-27)**: **finding #4 investigated, correction made, left
open.** Item #1's own text ("item #1's structured `must_conditions`/
`indicators_used` schema would dedup far more reliably than string
similarity once it exists") is now checkable, since item #1 landed
2026-09-26 — checked the real call site in `loop.py:315-339` rather than
assuming that fix carries over automatically.

- **It doesn't carry over as-is, and this is worth recording as a
  correction to finding #4's own text, not silently acted on**:
  `_match_score` runs at `run()`'s very start, matching the incoming
  free-text `user_idea` string against each existing hypothesis's
  `strategy_type` — which is itself just `user_idea` from whichever
  earlier call created it (`self._current_hypothesis.strategy_type =
  user_idea`, line 338). No `indicators_used`/must-condition data exists
  yet at this point in any hypothesis being matched *against* the new
  idea's string, because that field only gets populated *after* a
  research run actually determines what indicators the resulting
  strategy uses — dedup happens before the very information finding #4
  proposed matching on is computed. Structured `indicators_used`
  comparison is a real option for a *different* dedup question (do two
  *already-researched* strategies overlap), not a drop-in replacement
  for this token-overlap-on-free-text check at idea-submission time.
- Left unfixed, deliberately: swapping this for a better free-text
  idea-similarity check (a real embedding-similarity dedup, or a
  different threshold/tokenization) is itself a genuine, undecided
  design call this file's own discipline says to flag rather than
  invent unilaterally — the token-overlap heuristic's specific
  replacement isn't specified anywhere in this repo, only the (as it
  turns out, inapplicable-here) `indicators_used` idea.

**UPDATE (2026-09-27, later same day)**: **built, on explicit
instruction to invent a real replacement** rather than leave the design
call open. Two tiers, cheapest first, not a single new statistic swapped
in for the old one.

- **Tier 1 — TF-IDF cosine similarity** (new `idea_similarity.py`): the
  same algorithm `vinu-news`'s own `analysis/post_enrichment/cosine_dedup/`
  already uses for this exact class of problem (short-text duplicate
  detection) — reimplemented independently rather than cross-imported
  (neither service depends on the other's package, same convention as
  every other shared idiom reimplemented per-service this session).
  Downweights common words, upweights distinctive ones, unlike the old
  raw overlap ratio. Used as a cheap screen: a candidate with essentially
  no shared vocabulary at all is skipped without spending an LLM call on
  it (calibrated empirically — unrelated idea pairs scored 0.0-0.09 in a
  small hand-built test set, real conceptual overlap scored 0.25+).
- **Tier 2 — an LLM tie-breaker for the real semantic judgment** a bare
  similarity score can't reliably make: "SMA crossover" and
  "moving-average crossover" share almost no literal tokens but are the
  same idea; two different RSI strategies share the word "RSI" but
  aren't. New `ResearchLlmClient.check_duplicate_idea()` (`llm.py`,
  same `_traced_chat` convention every other LLM call in this class
  already uses) sends the new idea plus every candidate that passed the
  Tier 1 screen in **one call** (not one call per candidate), asks which
  index (if any) is a genuine duplicate, and is told explicitly to say
  "not a duplicate" when unsure — a missed duplicate costs one wasted
  research run, a false one corrupts two different ideas' evidence
  together, which is worse.
- **The LLM's explicit "not a duplicate" is trusted, not second-guessed**
  by falling back to the similarity score anyway — that would defeat the
  entire point of asking a better judge. The similarity-threshold
  fallback only fires when the LLM isn't configured or the call itself
  fails, so this still does something better than the old bare
  token-overlap even without an LLM available, rather than becoming a
  silent no-op.
- `_match_score` removed from `loop.py` entirely (confirmed dead after
  this — its only other appearance, `llm_generator.py`'s own
  same-named-but-unrelated helper for a different matching purpose, is
  untouched).
- 19 new tests: 10 in new `test_idea_similarity.py` (tokenize, TF-IDF
  weighting favoring distinctive terms, cosine similarity's identical/
  disjoint/empty-vector edge cases), 9 in `test_loop.py`
  (`TestMatchExistingHypothesis` — no existing hypotheses skips
  everything, an unrelated candidate never reaches the LLM, the LLM
  confirming a duplicate above its confidence floor, the LLM's explicit
  negative overriding what the fallback alone would have matched, a
  low-confidence LLM answer not matching, the LLM call failing falling
  back to the similarity threshold, the LLM not configured going
  straight to the fallback, a fallback score below threshold not
  matching, and every screened-in candidate — not just the top one —
  actually reaching the one LLM call). The old `TestMatchScore` class (4
  tests, for the now-removed function) was removed, not left testing
  dead code. Confirmed zero regressions: full `vinu-research` suite,
  1117 passed, 1 skipped, 0 failed (up from 1101 passed/1 failed after
  item #12 finding #2's own update — net +15 tests [+19 new, -4 removed]
  plus the one pre-existing flaky `test_concurrent_writes` passing on
  this particular run instead of failing, as it has intermittently done
  throughout this file).
- **This finding is now closed.**

**UPDATE (2026-09-27)**: **finding #2 fixed** — generation-time candidate
loss now has a real persistence surface, using the same shared
`RejectionRecord` shape (`vinu_infra.rejection_log`) as every other
instance of this recurring pattern, the same way item #23 finding #5 just
closed the portfolio-layer instance.

- New `vinu_research/generation_candidate_store.py`: `GenerationCandidateStore`,
  same two-table shape `sweep_store.py` already established (a
  `generation_rounds` header per call to `generate()`/`refine()`, a
  `generation_candidates` row per candidate drafted — winner included,
  flagged `chosen`, not just the losers). `LlmCandidate` carries no id at
  all (just code/params/reasoning), so a new `code_hash()` (truncated
  SHA-256 of the code string) is what identifies a candidate across
  rounds — enough to answer a first, narrow slice of finding #3's "has
  something like this already failed" question
  (`find_by_code_hash()`), not the full cross-death-point graveyard that
  finding describes (still a separate, bigger decision).
- **The one real design decision this needed, made explicitly, and
  deliberately the OPPOSITE default from item #3's `run_sweep_grid()`**:
  `StrategyResearchLoop.__init__`'s new `generation_candidate_store`
  param defaults to `None` (meaning "don't persist"), not a lazily-
  constructed default-path store. `run_sweep_grid()` is a standalone
  function called directly by an HTTP route/tool with no owning service
  object, so defaulting to always-persist-somewhere was the safe choice
  there; `StrategyResearchLoop` is always constructed by exactly one
  real owner (`ResearchService`), and is ALSO constructed directly, with
  no store, by dozens of existing tests — defaulting to always-persist
  here would have repeated item #3's own "tests start writing real
  files" near-miss at a much larger scale (loop.py's test file alone has
  ~70 tests). `ResearchService.__init__` injects a real store explicitly
  (same convention `strategy_store`/`signal_evidence_store` already use
  on that same constructor), which is the only place real generation
  calls ever happen.
- New private `StrategyResearchLoop._record_generation_round()`, called
  right after both of `_default_quant_coder`'s own `rank_candidates(...)`
  calls (iteration-1 generate, iteration-2+ refine) — the exact point
  the heuristic complexity-penalty ranking already happens and the
  losers already get discarded. Best-effort, never raises: a persistence
  failure must never break generation itself, same posture as every
  other side-write in this codebase.
- Wired to a real HTTP surface, not left as a store-only fix:
  `routes_introspect.py` (already the file for "give read access to
  state that was already being written but had no HTTP surface," per
  its own module docstring) gained `GET /research/generation-rounds`
  and `GET /research/generation-rounds/{generation_id}`. Caught and
  fixed a pre-existing, unrelated gap while there: this entire route
  file had zero dedicated tests before — not fixed wholesale (out of
  this finding's scope), but the two new routes got their own coverage
  rather than joining that gap.
- 24 new tests: 14 in new `tests/test_generation_candidate_store.py`
  (code-hash stability, round-trip, winner flagged and ranked first,
  every candidate recorded not just the winner, reasoning truncated,
  generate-vs-refine mode recorded distinctly, symbol-filtered listing,
  `find_by_code_hash` across multiple rounds), 5 in `test_loop.py`'s new
  `TestRecordGenerationRound` (no store injected is a total no-op, the
  generate path records every candidate with the winner flagged, the
  refine path records with `mode="refine"`, a broken store doesn't
  break generation itself, zero candidates never calls the store at
  all), 2 in `test_service.py` (`ResearchService` constructs a real
  store at its own `data_root`; an explicitly injected store is used
  instead of the default), and 3 in new
  `test_routes_introspect_generation_rounds.py` (empty list by default,
  unknown `generation_id` is 404, list-then-get after recording one
  round). Confirmed zero regressions and zero stray files: `test_loop.py`
  68 passed, `test_service.py`/`test_routes*.py`/`test_scheduled.py`/
  `test_integration_promotion.py` 133 passed, no `data/generation_
  candidates.db` (or any other store's file) left behind by any test —
  checked directly, not assumed, after the same near-miss item #3's fix
  had with `sweep_grid.db`.

## 17. Cross-service seam audit (2026-09-25) — agent↔research↔simulator, includes a real compound retry-storm risk

Previous audits (items 11-13) covered each service in isolation. This
one looks at the seams between them — where individual-component
correctness doesn't guarantee system-level correctness. Verified against
real code:

1. **A "surfaces the real error" code path is dead.**
   `vinu-infra/client.py:161-181`'s `ResilientClient.post` catches *any*
   exception (`except Exception: return fb`) before it can reach
   `vinu-research/tools.py:129-151`'s handler, which is specifically
   written to extract and re-raise the simulator's actual HTTP error
   detail as part of `InfrastructureError`. That handler's
   `httpx.HTTPStatusError` branch can never execute — the code's own
   comment claiming it "surfaces the simulator's own reason" is false.
   Every failure collapses into the same generic
   "simulator returned no result" message regardless of actual cause.
   Fix: `ResilientClient.post`/`get` should re-raise `HTTPStatusError`
   (or take a `raise_on_error` opt-in) instead of swallowing it.
2. **`InfrastructureError` is invisible the moment it crosses into
   `vinu-agent`.** `vinu_research/loop.py:366-395` correctly distinguishes
   "infra is down" from "no viable strategy found" internally, converting
   an `InfrastructureError` into a `CriticFeedback(verdict="STOP", ...)`
   — but the distinction lives only in free-text `reasoning`, never a
   structured field on `ResearchResult`. Grepped all of `vinu-agent/` for
   `InfrastructureError`/`"INFRASTRUCTURE FAILURE"`: zero hits. An
   automated scheduler with no LLM reading the prose
   (`scheduler_workers.py::run_team_for_ticker`) cannot tell "the
   simulator was down, try again later" from "we tested this for real and
   it's genuinely not a good strategy, reject it" — two responses that
   should be completely different, currently indistinguishable. Fix: add
   a structured `status: "infra_failure" | "no_strategy_found" |
   "passed"` field.
3. **The agent-side tool masks real failures via a blanket retry.**
   `research_tool.py:59-68` catches *any* exception from an in-process
   run — including a genuine bug or a raised `InfrastructureError` — and
   silently re-runs the entire multi-iteration research loop again over
   HTTP, visible only at DEBUG log level. Fix: narrow the except clause
   to actual infra/import errors, not a blanket catch.
4. **Timeout mismatch**: `run_sweep_candidate_tool.py:120` times out at
   180s; underneath, `vinu_research/tools.py:40-43`'s simulator client has
   its own `timeout=120.0, max_retries=3` — a legitimately slow-but-alive
   call can validly exceed 180s once retries are counted. Fix: the
   agent-side timeout should exceed research's own worst-case retry
   budget, or research should switch to an ack-then-poll pattern for this
   call.

**The compound risk, worth naming even though no single item states it**:
#3 and #4 together create a genuine retry-storm path. Research is still
validly working through its own retry budget when the agent's 180s
timeout fires; per #3, the agent doesn't distinguish "timed out because
research is still legitimately retrying" from "a real failure" — it just
re-runs the *entire* research loop over HTTP again, stacking a duplicate
expensive multi-iteration run on top of the original one still running
underneath. Under sustained load or a slow simulator day, this could
cascade into piled-up duplicate backtests — exactly the kind of failure
mode invisible in normal testing that surfaces the first time this
system runs unattended for real (item #16's autonomy scenario).

**Checked and confirmed fine**: auth is consistent across both hops —
both use `internal_auth_headers()` (`vinu-infra/auth.py:29-38`), no
skipped step found. **Confirmed gaps, not new items**: no
contract/schema test exists between any of the three services (only an
unrelated `test_signal_contract.py` in `vinu-initial-analysis` turned up);
no `policy_version`/schema-version field threads through the whole
agent→research→simulator chain, so a schema change on one side has
nothing automated to catch it before silently breaking the other.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed.

**UPDATE (2026-09-26)**: **findings #1 and #3 are now built and tested —
the two halves of the compound retry-storm risk this item names.**

- **Finding #1**: `ResilientClient.get`/`post` (`vinu-infra/client.py`)
  gained an opt-in `raise_on_error: bool = False` parameter, exactly the
  second option this finding's own fix text offered ("or take a
  `raise_on_error` opt-in"), chosen over unconditionally re-raising
  `HTTPStatusError` for every caller since `ResilientClient` has 15+
  call sites across the monorepo that rely on today's graceful-fallback
  behavior — the default stays `False` so none of them change behavior.
  `vinu-research/tools.py`'s `run_backtest()` (the one call site this
  finding is actually about) now passes `raise_on_error=True`, so its
  own already-written `except httpx.HTTPStatusError` branch — previously
  dead code, exactly as this finding said — can finally run and extract
  the simulator's real error detail instead of every failure collapsing
  into the generic "simulator returned no result" message.
- **Finding #3, and the concrete manifestation of the compound risk**:
  narrowing `research_tool.py`'s blanket `except Exception` (which
  masked a real `InfrastructureError` from `run_research()`'s own
  multi-iteration loop and silently re-ran the whole thing over HTTP)
  turned up something worth being precise about. `vinu_research/loop.py`
  already catches `InfrastructureError` from a backtest *internally*
  (finding #2's own point: it becomes a `CriticFeedback(verdict="STOP",
  ...)` inside a normal-looking result, never a raised exception) — so
  `research_tool.py`'s fix mostly guards against *other* real bugs, not
  that specific path. **`run_sweep_candidate_tool.py` is where the
  compound risk in findings #3+#4 is actually concrete**: unlike
  `run_research()`, nothing in `vinu_research/sweep.py`'s
  `run_sweep_candidate()` catches `InfrastructureError` from
  `tools.run_backtest()` — it propagates straight through, straight into
  this tool's own identical blanket `except Exception`, straight into a
  silent duplicate HTTP call at this exact file's own 180s timeout
  (finding #4's number) on top of the run that already failed for a real
  reason. Both `research_tool.py` and `run_sweep_candidate_tool.py`
  narrowed their except clause to `ImportError` — the one legitimate
  reason for the HTTP fallback documented in
  `vinu_agent/broker/research_link.py`'s own module docstring ("If
  vinu-research is not importable, every in-process call site here
  raises and its own try/except falls back to HTTP") — so a real
  `InfrastructureError`, or any other genuine bug, now propagates to
  `ToolRegistry.execute()`'s own `except Exception`
  (`vinu_agent/agent/tools.py`), which already turns it into a proper
  `{"status": "error", ...}` response instead of a silent duplicate run.
- Existing tests in both files simulated "in-process unavailable" with a
  generic `RuntimeError` -- updated to `ImportError` to match what
  actually triggers the fallback now, plus new regression tests in both
  files proving a real `InfrastructureError` (and, for
  `research_tool.py`, a generic bug too) propagates instead of
  triggering a duplicate HTTP call (`mock_post.assert_not_called()`).
  4 new tests total in `vinu-agent` (2 in `test_research_tool.py`, 1 in
  `test_run_sweep_candidate_tool.py`, plus the existing-test rewrites),
  6 new tests in a new `vinu-infra/tests/test_client.py` (nothing
  covered `ResilientClient`/`CircuitBreaker` at all before this).
  Confirmed zero regressions: `vinu-infra` 299 passed, `vinu-research`
  992 passed/1 skipped, `vinu-agent` 1345 passed (up from 1342, exactly
  +3 -- the pre-existing 16 failures/2 errors in `test_llm.py`/
  `test_service.py`/`test_capital_allocator_hook.py` are unchanged and
  confirmed unrelated).
- **What this item leaves open**: finding #2 (a structured
  `status: "infra_failure" | "no_strategy_found" | "passed"` field on
  `ResearchResult`, so an automated scheduler doesn't need to parse
  `reasoning` prose) and finding #4 itself (the actual timeout-budget
  mismatch between the agent's 180s and research's own worst-case retry
  time) are untouched — #2 is a real schema-design decision, and #4 on
  its own no longer causes a *silent duplicate run* (finding #3's fix
  means a real failure now surfaces as an error instead of retrying),
  but the raw timeout-budget mismatch itself is still there.

**UPDATE (2026-09-26, later same day)**: **finding #2 is now built and
tested** — the exact 3-state field this finding's own text specified,
named `outcome_status` (not `status`) to avoid a silent collision with
`service.py`'s existing, unrelated `status` key (the run's own
lifecycle state — pending/failed/completed — a different concept
entirely).

- `models.py`'s `ResearchResult` gained `outcome_status: str = ""`
  (empty, not `"passed"`, so a construction site that forgets to set it
  is visibly wrong rather than silently claiming success).
- `loop.py`'s new `_classify_outcome_status(history, best_result)` reads
  the *last* history entry's critique reasoning for the
  `INFRASTRUCTURE FAILURE` prefix (the one existing signal that already
  distinguishes an infra `STOP` from a genuine quality-based `STOP` —
  `CriticFeedback` itself has no separate structured field for this
  either, so this is honestly still a string match, just centralized
  behind one shared `INFRA_FAILURE_REASONING_PREFIX` constant instead of
  a magic string duplicated at the one place that sets it and the one
  place that reads it back). Falls back to `"no_strategy_found"` when
  `best_result` is `None`, else `"passed"`.
- **A 4th real case the audit's own 3-state enum doesn't name**: the
  symbol-exhausted early-return path (a skip, not an attempt) — classified
  as `"no_strategy_found"` (the closest fit: no strategy comes out of
  this call either way) rather than inventing a 4th enum value beyond
  what the finding specified.
- **Wired to where a scheduler would actually read it**: `service.py`'s
  `run_research()` response dict gained `"outcome_status": result.outcome_status`
  right next to (not replacing) the existing `"status"` key — confirmed
  by tracing the value forward before calling this done, not just
  adding the field and assuming it reaches something: `research_tool.py`
  (`vinu-agent`) returns this same dict via `json.dumps(result, ...)` for
  its in-process path, and the raw HTTP response body for its fallback
  path — both already pass this field through unchanged, so no further
  changes were needed there for it to actually reach a caller.
- 6 new tests: 5 in `test_loop.py` (`TestClassifyOutcomeStatus` — infra
  failure classified correctly, a genuine quality-based `STOP` with no
  `best_result` is *not* misclassified as infra just because both cases
  have `best_result=None`, no history at all, a real passing result
  after earlier `REFINE` iterations, and an infra failure on the *last*
  iteration overriding an earlier-looking-fine history), plus one
  extending the real, pre-existing `test_loop_returns_early_when_exhausted`
  integration test (`test_integration_exhaustion.py`) to confirm the
  actual early-exit `ResearchResult` carries `outcome_status ==
  "no_strategy_found"`, not just a unit-level classifier check.
  Confirmed zero regressions: full `vinu-research` suite, 1027 passed, 1
  skipped (up from 1022, exactly +5 net — the exhaustion test was
  extended, not added).
- **What this item leaves open now**: finding #4 itself (the raw
  timeout-budget mismatch) remains untouched, unchanged from the earlier
  note above.

**UPDATE (2026-09-26, later same day)**: **finding #4 fixed** — the
first of this finding's own two fix options (raise the agent-side
timeout above research's own worst-case retry budget), not the second
(switch to ack-then-poll — a real architecture change, not warranted for
a mismatch this precisely bounded).

- Computed the actual worst case rather than guessing a bigger number:
  `run_sweep_candidate_tool.py`'s HTTP fallback wraps exactly one call to
  `vinu_research.sweep.run_sweep_candidate()`, which calls
  `ResearchTools.run_backtest()` exactly once, which calls
  `self._simulator_client.post(...)` exactly once (all three confirmed
  by reading the call chain, not assumed) — `_simulator_client` is a
  `ResilientClient(timeout=120.0, max_retries=3)`. `vinu-infra/client.py`'s
  own retry loop: 3 attempts at up to 120s each, plus exponential backoff
  between attempts 0→1 and 1→2 (`retry_backoff=1.0`: `1.0*2**0 +
  random.uniform(0,1.0)` then `1.0*2**1 + random.uniform(0,1.0)`, capping
  at 2.0 + 3.0 = 5.0s) — worst case `3*120 + 5.0 = 365.0s`, against the
  old hardcoded `180`. A legitimately slow-but-alive simulator retrying
  its second or third attempt could and would exceed 180s.
- `run_sweep_candidate_tool.py`: new `_SIMULATOR_WORST_CASE_SEC = 3 *
  120.0 + 5.0` and `_SWEEP_CANDIDATE_TIMEOUT_SEC = _SIMULATOR_WORST_CASE_
  SEC + 35.0` (a fixed margin for the agent↔research HTTP round-trip and
  server-side work either side of the simulator call itself, not just a
  bump "by feel") replace the bare `180` literal at the actual
  `httpx.post` call site.
- 1 new test (`test_http_fallback_timeout_exceeds_the_simulator_clients_
  own_worst_case_retry_budget`): asserts the computed worst-case constant
  equals exactly 365.0 (a regression guard on the derivation itself, not
  just "some timeout is passed"), that the real timeout exceeds it, and
  that the actual `httpx.post` call site receives that exact value.
  Confirmed zero regressions: `test_run_sweep_candidate_tool.py` 13
  passed (up from 12, exactly +1); full `vinu-agent` suite otherwise
  unaffected (pre-existing, unrelated `ModuleNotFoundError: openai`
  failures in `test_llm.py`/`test_service.py`/`test_capital_allocator_
  hook.py` confirmed present in this same environment before this change
  too, not introduced by it).
- **This item is now fully closed** — findings #1, #2, #3, and #4 all
  fixed across this and earlier updates.

**UPDATE (2026-09-27)**: **the first of the two "confirmed gaps, not new
items" is now closed** — a real contract test now exists between all
three services, checked-in as two files, one per hop, mirroring how the
seam itself is actually two independently-maintained hops rather than
one.

- **Hop A (agent→research)**, new `vinu-agent/tests/test_research_contract.py`:
  exercises `research_tool.py`'s and `run_sweep_candidate_tool.py`'s REAL
  payload-building code (via the same HTTP-fallback path every other
  test in this suite already forces) and validates the actual dict each
  builds against vinu-research's own real pydantic request models
  (`RunResearchRequest`/`SweepCandidateRequest`) — not a hand-copied
  literal of what the schema "should" look like, which is exactly the
  kind of drift this gap warned about. Also directly proves
  `run_sweep_candidate_tool.py`'s own comment claim ("exactly
  `routes_sweep.py`'s own `_serialize` shape") rather than trusting a
  comment that could silently go stale if either side changed alone.
- **Hop B (research→simulator)**, new
  `vinu-research/tests/test_simulator_contract.py`: exercises
  `ResearchTools.run_backtest()`'s REAL body-building code (only
  `_simulator_client.post` itself is faked) and validates the body
  against vinu-simulator's own real `CustomSimulateRequest`; also
  confirms `run_backtest()`'s hardcoded `required = [...]` response-field
  list is actually a real subset of `CustomSimulateResponse`'s fields,
  not an assumption that could drift if a field were ever renamed.
- Both hops are import-based (validate against the real pydantic model
  directly), not integration tests that stand up either real server —
  deliberately: a schema-drift catch needs to run in each service's own
  fast unit-test suite, not a slower, separately-maintained end-to-end
  harness.
- 9 new tests total (6 in the agent-side file, 3 in the research-side
  file). Confirmed zero regressions: full `vinu-research` suite, 1097
  passed, 1 skipped (up from 1094, the +3 from this file, same
  pre-existing flaky `test_concurrent_writes` unrelated); full
  `vinu-agent` suite otherwise unaffected (same pre-existing 16
  failures/2 errors documented throughout this file).
- **What this leaves open**: the second "confirmed gap" (no
  `policy_version`/schema-version field threading through the whole
  chain) remains untouched — a real, separate design decision about how
  such a field would even be versioned/enforced, not a test-writing task.

## 18. vinu-screener audit (2026-09-25) — Layer 1, process/logic and code-level, not yet acted on

Real structure: two parallel surfaces sharing common machinery —
`ScanRule`/`ScanMonitor` (continuous condition-tree polling) and
`RankerConfig`/`RankerRunner`/`ScreenPipeline` (factor-weighted:
coarse-filter → hard-filter → score → risk-veto → concentration-adjust →
rotate → rank into top-N). Consumed by
`vinu-agent/tools/screener_client.py::fetch_screener_top_tickers()` via
`/screener/rankers/{id}/latest` — output shape confirmed to match, no
mismatch found. **Point-in-time safety confirmed clean**:
`features/operators.py` uses only trailing `.rolling()`/`.ewm()`/
`.shift(+n)`, no forward-looking ops found anywhere. **Freshness
confirmed correct**: rankers recompute fresh per run, the pairlist cache
has an explicit 60s TTL with proper fail-open `stale: true` labeling —
no hidden staleness bug.

### Process/logic design issues

1. **No minimum-history gate on the ranker path — a real mismatch with
   what Track 1 needs.** `HardFilterConfig`
   (`vinu_screener/pipeline/hard_filter.py:32-45`) and `CoarseFilter`
   (`scan/universe.py:24-35`) have no `min_bars`/`min_history` field. The
   condition-tree path does derive and enforce `min_bars`
   (`scan/monitor.py:145,246-248`), but `RankerRunner._fetch_universe`
   (`rankers/runner.py:53-62`) only drops `None`/empty frames — a
   thinly-traded or recently-listed symbol with as few as 30 bars can
   land in the ranker's top-N even though `signal_evidence`
   (Track 1) needs `min_observations=70` before it does anything with
   that ticker. A selected ticker can flow all the way to Layer 2 and
   silently produce nothing. Fix: add `min_history_bars` to
   `HardFilterConfig`/`RankerConfig`, checked in `RankerRunner.run()`
   before scoring.
2. **No baseline liquidity floor by default on the ranker path.**
   `min_dollar_volume`/`min_volume` exist but default to `None` — an
   operator must explicitly configure a floor per-ranker; nothing
   protects Layer 5's position sizing from an illiquid name slipping
   through if one isn't set. Low severity (configurable), worth a
   documented safe default.
3. **Per-symbol "why rejected" is computed then discarded before
   persistence.** `Candidate.veto_reason`/`dropped_at` and
   `hard_filter_reasons()` (`pipeline/hard_filter.py:75-95`,
   `rule_filters.py:90-95,124-127`) capture exactly why each candidate
   was cut — but `RankedSnapshotStore.set_latest`
   (`rankers/snapshot_store.py:86-106`) only persists survivors (`top`,
   with their full factor breakdown and risk flags — good) plus
   aggregate before/after counts per stage, never per-symbol reject
   reasons. So "why was ticker X selected" has real rationale; "why was
   ticker Y excluded" is unrecoverable after the run — directly relevant
   to the "why" schema work in `03-strategy-definition-full-schema.md`,
   which can explain a chosen strategy's reasoning but has nothing to
   inherit from a ticker that never made it that far. Fix: persist a
   bounded sample of `dropped_at`/`veto_reason` per stage alongside the
   existing trace.

### Code-level issues

4. **The exact indicator-duplication mistake, again, in a new
   component.** `vinu_screener/features/operators.py:35-96`
   reimplements `sma`/`ema`/`rsi`/`macd`/`wma`/`std` independently —
   a third copy of logic that already lives correctly in
   `vinu-tools/vinu_tools/compute/indicators/`, the same class of bug
   `06-mistake-duplicated-indicator-logic.md` already documented and
   fixed once for Track 1. If the screener's RSI smoothing or EMA
   `adjust` flag differs even slightly from `vinu-tools`', the screener
   ranks tickers on subtly different numbers than the rest of the
   pipeline analyzes them with. Fix: have `features/library.py` delegate
   to `vinu_tools.compute.indicators`, or explicitly document why a
   second implementation is intentional if it must stay (e.g.
   pandas-vectorized vs. list-based performance reasons).
5. **No test would catch finding #1.** Unit tests on scoring/filtering
   (`test_scorer.py`, `test_hard_filter.py`, `test_pipeline.py`,
   `test_rule_filters.py`) are solid at the unit level, but nothing
   exercises `RankerRunner.run()` end-to-end with a real multi-symbol
   OHLCV fetch — exactly the integration point where the missing
   history-gate lives.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed.

**UPDATE (2026-09-26)**: **finding #1 is now built and tested**, built
exactly as the finding's own fix specified — a `min_history_bars` field,
checked in `RankerRunner.run()` before scoring.

- `pipeline/hard_filter.py`'s `HardFilterConfig` gained `min_history_bars:
  int | None = None` — not one of `_BOUND_FIELDS` (those read a `fields`
  value already computed from the OHLCV frame; this reads the frame's own
  bar count directly, before any factor computation happens at all).
  `RankerConfig.from_dict`/`to_dict` already thread `HardFilterConfig`
  through generically (`HardFilterConfig(**raw.get("hard_filter", {}))`/
  `asdict`), so no separate `RankerConfig` wiring was needed for the new
  field to round-trip.
- `rankers/runner.py`'s new `RankerRunner._apply_min_history_gate()` runs
  right after `_fetch_universe()`, before `self._factory.latest(...)` —
  the same "gate before the expensive work" point the condition-tree
  path's own `required_bars`/`insufficient_history` (`scan/monitor.py`)
  already enforces for its own surface; this is the ranker path's
  equivalent, using an explicit config field instead of deriving a
  requirement from a condition tree (there isn't one on this path).
  Dropped symbols are logged at INFO (`"insufficient history"`, matching
  the condition-tree path's own vocabulary) rather than silently
  vanishing — a real, if partial, answer to this item's "a selected
  ticker can flow all the way to Layer 2 and silently produce nothing"
  complaint; the fuller per-symbol rejection-reason persistence finding
  #3 describes is a separate, bigger fix, not attempted here.
- 4 new tests in `tests/test_ranker_runner.py`
  (`TestMinHistoryGate`): below-bound excluded, exactly-at-bound kept
  (confirms the comparison is `>=`, not `>`), unset field is a no-op
  (default behavior unchanged), and a log-visibility test confirming a
  dropped symbol's name and reason actually appear in the log rather
  than vanishing silently. Confirmed zero regressions: full
  `vinu-screener` suite, 440 passed (up from 436, exactly +4).
- **What this item leaves open**: finding #2 (no default liquidity floor,
  low severity/configurable), finding #3 (per-symbol rejection reasons
  discarded before persistence, a bigger cross-cutting fix — see item
  #21's same pattern), and finding #4 (the screener's own hand-rolled
  `sma`/`ema`/`rsi`/`macd`/`wma`/`std`, a 5th confirmed instance of the
  indicator-duplication pattern already fixed once in item #20) are
  untouched.

**UPDATE (2026-09-26, later same day)**: **finding #2 addressed, but
deliberately as a documented recommendation, not a changed class
default.** Flipping `HardFilterConfig`'s own default would silently
change the live behavior of any already-configured ranker that
currently has no floor set (`RankerConfig.from_dict`'s
`HardFilterConfig(**raw.get("hard_filter", {}))` picks up a dataclass
default change on the very next load) — a real, hard-to-reverse
behavior change this finding's own "low severity, worth a documented
default" framing doesn't actually ask for. Found a real number already
in this codebase to point to instead of inventing one:
`rankers/seed.py`'s `CORE_STARTER_HARD_FILTER` already answers "what's a
reasonable floor" for the one ranker that ships seeded by default
(`min_price=5.0, min_dollar_volume=1_000_000.0`) — `HardFilterConfig`'s
own docstring now names this as the recommended pair of numbers for any
*new* ranker, unless there's a specific reason not to. Docs-only change,
no behavior change, no test suite to re-run. Findings #3 and #4 remain
untouched.

**UPDATE (2026-09-26, later same day)**: **finding #4 investigated and
partly fixed** — checked each of the six named functions against its
`vinu-tools` counterpart individually rather than assuming they all
diverge the same way `adx`/`atr` did in item #20.

- `sma()`/`ema()`/`macd()` (`features/operators.py`) compute the exact
  same formula as their `vinu-tools` counterparts (verified by reading
  both, not assumed) — duplicated *code*, but not a numeric-divergence
  risk, so nothing to fix there beyond the maintainability nit the
  finding already named.
- `wma()` has no `vinu-tools` counterpart at all — not actually a
  duplicate.
- `std()` (wired to raw `close` via `library.py`'s `IndicatorSpec("std",
  ("close",), op.rolling_std)`) turned out to be measuring a different
  *feature* than `vinu-tools`'s `volatility_20d` — that one is rolling
  std of daily *returns*, this one is rolling std of the price level
  itself. Not the same indicator under two names, so no cross-consistency
  issue exists here to fix, unlike this finding's blanket framing implied.
- `rsi()` was the one real, confirmed divergence, and the actual
  numeric-correctness risk this finding warns about: it used
  `ewm(alpha=1/period, adjust=False)` seeded from bar 0, while
  `vinu_tools.compute.indicators.rsi`'s own `_rsi()` uses true Wilder
  seeding (a plain mean of the first `period` real diffs, then recursive
  smoothing) — same decay rate, different seed, so this screener ranked
  tickers on slightly different early-window RSI numbers than Track 1's
  own RSI reading of the same bars (the exact risk this finding's own
  text names). Fixed in place to match `_rsi()`'s algorithm exactly —
  verified index-for-index identical output against `_rsi()` on a 60-bar
  random series before landing, not just "looks close."
- Full delegation to `vinu-tools` (rather than porting the one divergent
  formula in place) deliberately not done: `vinu-screener` has no
  existing dependency on the `vinu-tools` package at all — adding one is
  a real new cross-service dependency, a bigger call than this finding's
  scope — and `vinu-tools`'s `compute(rows: list[dict], ...)` shape is
  row-based, not composable with `operators.py`'s pandas-`Series`-in/
  `Series`-out shape the way this module's Qlib-style operator chaining
  (`slope(ema(s, 12), 5)`, etc.) needs. A real architecture mismatch, not
  just a missing import — left open, matching this finding's own
  documented-alternative framing ("or explicitly document why a second
  implementation is intentional").
- 2 new tests in `tests/test_operators.py` (`TestRSI`): an
  index-for-index match against `vinu_tools`'s own `_rsi()` on a 60-bar
  random series, and a warmup-boundary check (`NaN` for the first
  `period` bars, a real value from bar `period` on). Confirmed zero
  regressions: full `vinu-screener` suite, 442 passed (up from 440,
  exactly +2).

**UPDATE (2026-09-26, later same day)**: **finding #3 fixed, built as
item #21 pattern #3's own shared shape rather than a one-off** — this is
the screener instance of that cross-cutting pattern's fix, using the
`RejectionRecord` shape that section's own text already specified so the
same shape can serve item #3/#16.2's instances too if built later.

- New `vinu_infra/rejection_log.py`: `RejectionRecord` (`entity_type,
  entity_id, stage, rejection_category, rejection_detail,
  compared_against_id, timestamp`) + `record_rejection(...)`, a pure
  constructor — deliberately not a shared table. Pattern #3's own text
  is explicit about this: "different components can each store rows in
  their own existing storage, but all through the same write
  function/schema."
- Tracing this to a real fix turned up a deeper gap than the finding's
  own text described: `Candidate.veto_reason` is what `RiskVetoRule`
  sets on a drop, but `HardFilterRule.apply()` computed
  `hard_filter_reasons()` and never attached it to the candidate at
  all — the specific reason wasn't just undiscarded-but-unpersisted, it
  never survived past the `if reasons:` branch inside `apply()` itself.
  Fixed by setting `c.veto_reason` there too (reusing the existing
  field, not adding a new one — "why this candidate was dropped" means
  the same thing for both filter stages).
- `FilterChain.run()` now diffs each stage's before/after candidate sets
  by symbol (rather than changing every `ScanFilter.apply()`'s own
  return contract) to collect a bounded sample (`MAX_REJECTED_SAMPLE_
  PER_STAGE = 20` — a universe-wide scan can drop hundreds of symbols
  per stage; this is for "why was ticker Y excluded" visibility, not a
  full audit log) of the candidates each stage actually dropped, still
  carrying their own `dropped_at`/`veto_reason`. Its return type changed
  from a 2-tuple to a 3-tuple — the one call site (`ScreenPipeline.run()`)
  and two existing tests that unpacked it were updated to match.
  `ScreenPipeline.run()` converts these into `RejectionRecord` dicts
  (`entity_type="screener_symbol"`) and exposes them as
  `PipelineResult.rejected_samples`.
- **A second, independent bug found and fixed while wiring this through
  to the real HTTP consumer, not assumed already working**:
  `RankerSnapshot.to_dict()` — the exact method both `POST .../rank` and
  `GET .../latest` serialize their response through — never included
  `trace` at all, despite `trace_json` already being a real column and
  `RankerSnapshot.trace` already being populated by `get_latest()`. The
  per-filter-stage counts were computed, stored, and reconstructed, then
  stranded one method call from the actual API response the whole time.
  Fixed alongside adding `rejected_samples` to the same dict, since both
  are the same class of "reaches the store but not the response" gap.
  New `rejected_json` column (migration, `SCHEMA_VERSION` 2 -> 3),
  threaded through `set_latest()`/`get_latest()` the same way
  `trace_json` already is, including the same fail-open-to-`[]` handling
  for a pre-migration row.
- 15 new tests: 3 in `test_rule_filters.py` (hard-filter reasons attached
  to the dropped candidate, the per-stage sample bounded at exactly
  `MAX_REJECTED_SAMPLE_PER_STAGE`, no entry for a stage that drops
  nothing) plus updating 2 existing tests for the 3-tuple return; 1 in
  `test_pipeline.py` (`rejected_samples` traced end-to-end from a real
  hard-filter drop); 4 in `test_ranker_snapshot_store.py`
  (`TestRejectedSamplesRoundTrip` — round-trip, empty case,
  `to_dict()` inclusion, pre-migration fail-open); 2 in
  `test_server_app.py` (the real HTTP response for both `/rank` and
  `/latest` includes `rejected_samples`); 6 in `vinu-infra`'s new
  `test_rejection_log.py`. Confirmed zero regressions: full
  `vinu-screener` suite, 452 passed (up from 442, exactly +10 net — 15
  new plus 2 updated, minus 0 removed, matching the file-by-file count
  above once the 2-tuple-to-3-tuple updates are counted as edits, not
  new tests); full `vinu-infra` suite, 311 passed (includes the 6 new
  `rejection_log` tests).
- **This item is now fully closed** — all 4 findings addressed: #1 and #3
  built, #2 addressed as a documented recommendation, and #4 resolved by
  checking each named function individually rather than a blanket fix
  (`rsi()` fixed, `sma`/`ema`/`macd` confirmed already-matching,
  `wma`/`std` confirmed not actually duplicates). The one thing left on
  the table is finding #4's full-delegation *alternative* (switching
  `operators.py` to call `vinu-tools` directly) — explicitly optional per
  that finding's own text, not a numbered gap still open.

## 19. vinu-stock-price and vinu-news audit (2026-09-25) — Layer 2 data providers, includes the most serious point-in-time finding in this series

Real, verified findings. The news finding is flagged as the single most
important item in this whole file so far — a silent look-ahead-bias risk
in the data foundation everything else backtests against, not a
"someday" cleanup item.

### vinu-stock-price

1. **No server-side as-of enforcement anywhere — HIGH.**
   `vinu_stock/server/routes_read.py:77-115`'s `/candles/{symbol}`
   accepts arbitrary `to_ts`/`days` with zero cap against "now." Grepped
   the whole service for `as_of`/`asof`/`clamp`/`cutoff`: zero hits
   outside backfill comments. Point-in-time safety exists *only* because
   `vinu-agent/tools/stock_price_tool.py:47-62` remembers to clamp
   client-side (already flagged as untested in item #11.2) — there is no
   server-side safety net if any future caller forgets. Fix: add a
   server-side `as_of` query param that hard-caps `to_ts` independent of
   caller discipline.
2. **Gap detection only runs during backfill, invisible to live query
   callers.** `catalog/gap_validation.py`'s `count_session_gaps` is only
   called from `backfill/year_job.py:47`. The `/candles/{symbol}` read
   path never checks or surfaces gaps — a mid-range gap (vendor outage,
   missed fetch) looks identical to "the market was closed that day."
   Only a *fully* empty result gets a header at all
   (`routes_read.py:106-114`). Fix: surface gap info on every serve, not
   just backfill.
3. **A 4th instance of the indicator-duplication pattern.**
   `vinu_stock/query/indicators.py:46-90` reimplements SMA/RSI/MACD/
   volatility/ADX from scratch instead of using `vinu-tools`'s shared
   library — the same `06-mistake-duplicated-indicator-logic.md` class of
   bug, now found in vinu-screener AND vinu-stock-price independently
   (see item #18.4 for the screener instance). Two implementations with
   different warm-up/NaN handling can silently produce different values
   for what should be the same indicator.
4. **`yfinance` provider has no retry/backoff**, unlike every other
   provider in the same directory (`yahoo.py`, `polygon.py`, `alpaca.py`,
   `tushare.py`, `finnhub_provider.py` all correctly route through
   `vinu_infra.retry`'s shared helper) — the same yfinance-flakiness
   pattern already flagged for `vinu-agent`'s `fundamentals_tool.py`
   (item #11.3).
5. Minor: cache TTL (300s) means a "live" caller polling an open-ended
   window can get up to 5-minute-stale data with no staleness flag in the
   response.

### vinu-news — the standout finding

1. **Publish time and ingestion time are silently conflated, with no
   flag recorded when this happens — the most serious point-in-time
   finding in this file so far.** `ArticleRecord`
   (`analysis/storage/models.py:10-35`) has exactly one timestamp,
   `sort_ts`, used for every downstream filter, thread, and
   price-reaction alignment. It's set via `parse_pub_date()`
   (`analysis/storage/repository.py:297-300`), which **silently falls
   back to `datetime.now(timezone.utc)`** whenever a feed's `pubDate` is
   missing or unparseable — with no boolean/flag anywhere marking that
   this substitution happened. Worse, there is no separate `ingested_at`
   timestamp at all: if an article was genuinely published at time T but
   only fetched by the poller at T+2h (real crawl lag), a backtest
   replaying "as of T" would see news it could not actually have known
   about yet — genuine, silent look-ahead bias, baked into the data
   layer itself, not introduced by any consumer's mistake. Every
   downstream enrichment (sentiment, impact, threat scoring) inherits
   this risk since it's keyed to the same `sort_ts`. No test covers
   `parse_pub_date`'s fallback path or the ingestion-lag scenario. Fix:
   add both `published_at` and `ingested_at` columns, plus a flag when
   publish time was estimated via fallback — and treat any article with
   that flag as excludable from strict point-in-time replay.
   **Concrete schema addition, so this is buildable without re-deriving
   the shape later**, on `ArticleRecord` (`analysis/storage/models.py:10-35`):
   `published_at: str` (the real parsed pubDate, nullable),
   `ingested_at: str` (when the poller actually fetched it, always set,
   never estimated), `publish_time_is_estimated: bool` (true whenever
   `parse_pub_date()` hit its fallback path). Keep `sort_ts` as a
   derived/computed field (`published_at` if present and not estimated,
   else `ingested_at`) rather than removing it, so existing downstream
   readers of `sort_ts` don't all need to change at once — they can
   migrate to checking `publish_time_is_estimated` one at a time.
2. **Same server-side-clamp gap as stock-price** — `server/routes_read.py`
   has no as-of/cutoff parameter on any route (`/latest`,
   `/ticker/{symbol}`, `/watchlist/news`, `/high-impact`, `/search`);
   clamping is entirely client-side in `vinu-agent/tools/news_tool.py`.
3. **Checked and confirmed genuinely solid, not a gap**: cross-source
   dedup (`analysis/post_enrichment/cosine_dedup/`) does real
   similarity clustering with ticker/entity-overlap gating — not just
   the simpler exact-URL same-batch dedup. No finding needed here.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Given the severity of the news timestamp finding
specifically, this is a strong candidate to prioritize over several other
items in this file once the user decides to start fixing things.

**UPDATE (2026-09-26)**: **the news finding #1 (the most serious
point-in-time finding in this series) is now fixed and tested**, built
exactly to its own concrete schema spec.

- `analysis/storage/models.py`'s `ArticleRecord` gained the three fields
  the finding specified verbatim: `published_at: int | None` (the real
  parsed pubDate, nullable), `ingested_at: int` (always set, never
  estimated), `publish_time_is_estimated: bool`. `sort_ts` was kept, not
  removed, exactly as the finding recommended, so existing readers don't
  all need to migrate to the new fields at once.
- `analysis/storage/repository.py`'s `parse_pub_date` used to silently
  `return int(datetime.now(timezone.utc).timestamp())` on both its
  fallback paths (empty pubDate, unparseable pubDate) -- indistinguishable
  from a real parse from the caller's side. It now returns
  `tuple[int | None, bool]` -- `(None, True)` on either fallback path
  instead of fabricating a timestamp itself, pushing the actual "what do
  we use instead" decision to the caller rather than hiding it inside the
  parse function.
- `analysis/enrichment/enrich.py`'s `enrich_article` (the single real
  call site, confirmed by grepping the whole monorepo for
  `parse_pub_date`) now stamps `ingested_at` once, at the top, as this
  system's own real "now" -- then uses it as `sort_ts`'s fallback only
  when `published_at` came back `None`, instead of a second, independently
  fabricated timestamp. `publish_time_is_estimated` is threaded straight
  through onto the constructed `ArticleRecord`.
- **Storage wiring, not just the dataclass**: `ARTICLE_COLUMNS` and
  `_MIGRATION_COLUMNS` (the existing idempotent `ALTER TABLE` pattern
  this file already uses for `entities_json`/`cluster_id`/etc.) both
  gained the three new columns, and `schema.sql`'s `CREATE TABLE
  articles` gained them too, matching this repository's own existing
  dual-path convention (schema.sql for fresh installs, migration columns
  for existing databases) -- confirmed with a real round-trip test
  through `NewsRepository`, not just checked at the dataclass level.
- 7 new tests: `TestParsePubDate` (4, unit-level on the new tuple
  return), `TestPointInTimeMetadataOnEnrichedArticles` (2, through the
  real `enrich_article()` call chain -- one confirming a real pubDate
  sets `published_at`/leaves `sort_ts` derived from it, one confirming a
  missing pubDate flags `publish_time_is_estimated=True` and falls
  `sort_ts` back to `ingested_at`), and one in `test_persist.py`
  confirming the three columns survive a real SQLite
  insert-then-read-back through `NewsRepository`, not just the in-memory
  dataclass. Confirmed zero regressions: ran both the affected test
  files and the full `vinu-news` suite against a `git stash`-verified
  baseline both before and after -- identical pre-existing failure/error
  counts (9 failed, 29 errors, all `vinu_infra.config`/unrelated-provider
  issues confirmed present in the unmodified baseline too), passed count
  90 -> 97 (+7, exactly the new tests).
**UPDATE (2026-09-26, later same day)**: **vinu-stock-price finding #1
(the "HIGH"-severity one) and vinu-news finding #2 are now fixed**,
together with item #21 pattern #1 (the cross-cutting synthesis that
named this as a systemic gap, not two isolated ones) -- built as one
shared piece in `vinu-infra`, exactly as pattern #1's own fix direction
recommended, rather than as two separate per-service patches.

- New `vinu_infra/point_in_time.py`: `clamp_to_as_of(value, as_of)`, a
  single pure function -- not a decorator/middleware (the two services'
  existing route shapes already differ enough -- `to`/`from`/`days` vs.
  `to`/`from`/`days`, but every other read route in each service has yet
  another shape entirely -- that a generic wrapper would need to
  special-case each one anyway; a plain function call at the one place
  each route already computes its effective end achieves the same
  "no per-service reinvention" goal with far less framework-level risk).
  `as_of=None` never clamps (no replay boundary requested); an unset
  `value` under a real `as_of` becomes `as_of` itself, not `None` --
  the actual gap both services had: an unbounded query with no upper
  cap at all, not just a too-generous one.
- Wired into the one route in each service that already has an
  absolute-timestamp shape closest to a direct fit:
  `vinu-stock-price/server/routes_read.py`'s `/candles/{symbol}`
  (`to_ts`/`days`) and `vinu-news/server/routes_read.py`'s
  `/ticker/{symbol}` (`to`/`from`/`days`). Both gained an `as_of` query
  param and clamp the effective end before calling their own service
  layer, exactly per vinu-stock-price finding #1's own fix text ("add a
  server-side `as_of` query param that hard-caps `to_ts` independent of
  caller discipline"). A response header (`X-Clamped-To-As-Of: true`)
  signals when clamping actually happened -- the same out-of-band-header
  convention `/candles/{symbol}` already used for its `X-Data-Empty`
  flag, not a change to either route's existing `DataResponse` body
  schema (shared by other routes in both services).
- 6 new tests in `vinu-infra/tests/test_point_in_time.py` (the pure
  function), 4 new tests in `vinu-stock-price/tests/test_api.py`
  (`TestCandlesAsOfClamp`, through the real seeded-parquet `TestClient` —
  confirms bars after the boundary are excluded, an explicit `to` beyond
  `as_of` is still clamped, no `as_of` never clamps, and an `as_of`
  beyond all real data is a no-op), 5 new tests in a new
  `vinu-news/tests/test_ticker_news_as_of_clamp.py` (calling the route
  function directly against a fake service, with every `Query(...)`
  -defaulted parameter passed explicitly -- calling a FastAPI route
  function directly, bypassing its own request handling, means an
  omitted parameter carries the literal `Query(...)` sentinel object
  rather than its resolved default, caught by a real `TypeError` while
  writing these before being fixed). `vinu-news`'s own `TestClient`-based
  route tests (`test_api.py`) are pre-existing broken in this dev
  environment (`MissingDataRootError`, confirmed present in the
  unmodified baseline too, unrelated to this fix) — the direct-call unit
  tests are the real substitute here, not a downgrade chosen for
  convenience.
- Confirmed zero regressions: `vinu-infra` 305 passed (up from 299,
  +6), `vinu-stock-price` 119 passed (up from 115, +4),
  `vinu-news` 9 failed/102 passed/29 errors (up from 97 passed, +5,
  identical pre-existing 9 failed/29 errors to the baseline confirmed
  earlier in this same file's item #19 update).
- **What this item leaves open**: `/candles/batch` (vinu-stock-price)
  and vinu-news's other four read routes (`/latest`, `/watchlist/news`,
  `/high-impact`, `/search`) are relative `days`/`hours`-back-from-now
  windows with no existing absolute-end parameter at all -- extending
  `as_of` to them means first deciding how it interacts with each
  route's own existing relative-window semantics (does `as_of` become
  the new "now" anchor? what happens to `/latest`'s separate `date`
  param?), a real design decision this pass didn't make rather than
  invent unilaterally. Finding #2 (gap-detection visibility),
  finding #3 (indicator duplication), and finding #5 (cache staleness)
  on the vinu-stock-price side remain untouched, as does item #11.2's
  still-open ask to test vinu-agent's own client-side clamps (now a
  second layer of defense behind this server-side one, not the only
  one).

**UPDATE (2026-09-27)**: **finding #4 fixed** — `YFinanceProvider` now
retries on a transient failure instead of turning any network blip into
a permanent error, exactly the pattern item #11 finding #3 already
established for `vinu-agent`'s `fundamentals_tool.py` (the fix's own
code comment there had already named this item as the sibling instance).

- New `_retry()` helper in `vinu_stock/providers/yfinance.py`: 3
  attempts, 1s between, bare `except Exception` — deliberately **not**
  `vinu_infra.retry`'s HTTP helper every other provider in this
  directory uses, since its `exceptions=` tuple is `requests`-specific
  and wouldn't reliably match yfinance's own transient failure modes
  (same reasoning already applied on the `vinu-agent` side).
- Wraps only the real network call in each method — `ticker.history(...)`
  in `fetch_bars`, `ticker.info` in `earliest_available` — not the
  "valid empty answer" cases already handled below them. An empty
  DataFrame (no data in this range) and a missing
  `firstTradeDateEpochUtc` key are real, non-transient answers, not
  failures; retrying either would just waste wall-clock for the same
  result, so both stay outside the retry loop exactly as before.
- 8 new tests in new `tests/test_yfinance_provider.py` (this provider had
  zero test coverage before this fix): first-attempt success for both
  methods, a transient failure that retries then succeeds for both, a
  permanent failure that exhausts all 3 attempts before returning an
  error for both, and the two non-retried "valid empty answer" cases
  (empty DataFrame, missing `firstTradeDateEpochUtc`) confirmed to fetch
  exactly once with no sleep. `yfinance` isn't installed in this
  environment, so tests inject a fake module via `sys.modules` — same
  convention `test_fundamentals_tool.py` already established for this
  exact situation on the `vinu-agent` side.
- Confirmed zero regressions: full `vinu-stock-price` suite, 127 passed
  (up from 119, exactly +8).
- **What this item leaves open now**: finding #2 (gap-detection
  visibility), finding #3 (indicator duplication), and finding #5 (cache
  staleness) remain untouched.

**UPDATE (2026-09-27)**: **findings #2 and #5 both fixed** — the same
header-based "surface it, don't just log it" convention
`X-Clamped-To-As-Of`/`X-Data-Empty` already established on this exact
route, not a new response shape.

- **Finding #2**: `/candles/{symbol}` now calls the already-existing
  `count_session_gaps()` on the served rows (still only reachable from
  `backfill/year_job.py` before this) and sets `X-Session-Gap-Count`
  when it finds any — a mid-range gap no longer looks identical to "the
  market was closed." Deliberately scoped to `interval == "1m"` only:
  `count_session_gaps()`'s own `BAR_SEC=60` assumption doesn't generalize
  to aggregated intervals, and generalizing it was a bigger change than
  this finding asked for.
- **Finding #5**: `IndicatorCache.get()` now returns `(data, age_seconds)`
  on a hit instead of bare `data` (its only caller, `query/engine.py`,
  updated in the same pass) — the real property a "live" caller polling
  an open-ended window needed, not just the data. `fetch_candles()`
  gained an optional `cache_info: dict | None = None` out-param rather
  than changing its own `list[dict]` return shape (relied on by every
  other caller); `StockService.get_candles()` forwards it;
  `routes_read.py` sets `X-Cache-Age-Seconds` when a hit occurs. Only
  applies when `indicators` are requested — that's the only path this
  cache sits on.
- **A real, pre-existing test-isolation gap found and fixed while
  building this, not glossed over**: `query/engine.py`'s own frame cache
  (`_CACHED_FRAMES`, separate from the indicator cache above) is keyed by
  symbol only, with a 30-second cooldown before it even re-checks the
  file signature. Every test in `test_api.py` reuses symbol "AAPL" under
  a fresh `tmp_path` each time, so a later test could silently read an
  earlier test's cached frame — invisible until now because every
  existing test's assertions (bar count, header presence) happened to be
  shape-invariant across fixtures. The new gap-count tests, which check
  exact values, were the first sensitive enough to expose it. Fixed at
  the test level, not production: a new `autouse` fixture in
  `test_api.py` clears both this frame cache and the indicator cache
  before and after every test in the file.
- 12 new tests: 5 in `test_api.py` (`TestCandlesSessionGapHeader` — a
  missing minute sets the header, consecutive bars set none, a non-1m
  interval never computes it; `TestCandlesCacheAgeHeader` — a repeat hit
  reports its age, no `indicators` param never sets the header), 7 in new
  `tests/test_indicator_cache.py` (`IndicatorCache` had zero direct
  tests before this: miss, hit-with-real-age, TTL expiry, LRU eviction,
  different indicator sets are different keys, per-symbol and
  clear-everything invalidation). Confirmed zero regressions: full
  `vinu-stock-price` suite, 139 passed (up from 127, exactly +12).
- **What this item leaves open now**: only finding #3 (indicator
  duplication, the same pattern already fixed in `vinu-screener` item
  #18.4 and `trend_lifecycle` item #20.7) remains untouched on the
  `vinu-stock-price` side.

## 20. vinu-tools and other-angles audit (2026-09-25) — real formula bugs in ADX/ATR, directly relevant to Track 2's 2×ATR decision

Real, verified findings, including actual indicator formula bugs, not
just style/efficiency issues.

### vinu-tools

1. **ADX uses the wrong smoothing method.**
   `vinu_tools/compute/indicators/adx/adx.py:44-49` smooths TR/+DM/-DM
   using standard EMA (alpha=2/(period+1)) via `_shared/rolling.py`'s
   `ema()`. Real Wilder ADX requires Wilder's smoothing (alpha=1/period,
   aka RMA) — using standard EMA produces materially different values
   than any standard charting platform or TA-Lib. `rsi/rsi.py:48-53` in
   the same package *correctly* implements true Wilder smoothing, so this
   is an internal inconsistency, not a considered design choice — the
   codebase clearly knows the right method and didn't apply it here.
2. **ATR has the same class of bug — a third different smoothing
   convention.** `atr/atr.py:39` returns `sma(tr, period)` — plain SMA of
   true range, not Wilder-smoothed TR. So RSI, ADX, and ATR — three
   "Wilder-family" indicators in the same library — each use a
   *different* smoothing method, and only RSI is actually correct.
   **Directly relevant to Decision 14 (Track 2's 2×ATR(14) move-detection
   floor, `../how-to-use-29th-angle/03-move-detection-threshold-options.md`)**: if `atr_14` here
   isn't the standard Wilder-smoothed ATR, the actual threshold behavior
   won't match what "2×ATR" is normally understood to mean elsewhere.
   This should be fixed before Track 2 gets implemented, not treated as
   a later cleanup.
3. **Only 7 of 28 indicators have any correctness tests**
   (`tests/test_indicators.py`, 97 lines) — `sma`, warmup, `session`,
   `ichimoku`, `parabolic_sar`, `mfi`, `accumulation_distribution_line`.
   ADX and ATR, the two indicators with confirmed formula bugs above, are
   both untested — a basic known-value test would have caught both.
   **Concrete fix, so this is buildable without re-deriving Wilder's
   formula later**: `rsi/rsi.py:48-53` already implements the correct
   recursive pattern —
   `avg = (avg * (period - 1) + new_value) / period`, seeded by a plain
   average of the first `period` values (lines 48-49). This is exactly
   Wilder's smoothing (alpha=1/period); the fix for both ADX and ATR is
   to extract this exact recursion into a shared
   `wilder_smooth(values, period)` helper in `_shared/rolling.py`, then
   replace `adx.py:44-49`'s `ema()` call and `atr.py:39`'s `sma(tr,
   period)` call with it — copying RSI's already-correct logic, not
   inventing a new formula.
4. **Duplicated helper within the library itself**: `macd/macd.py` and
   `macd_signal/macd_signal.py` each independently define an identical
   `_macd()` helper, copy-pasted rather than shared from `_shared/`.
5. **Mostly unvectorized**: the indicator package is largely Python
   list-loops, not pandas/numpy-vectorized — e.g. `mfi/mfi.py:39-44` has
   a nested O(n×period) Python double-loop. Slow at the scale of many
   symbols × many indicators × long history.
6. **Likely root cause of all 4 duplication instances found across this
   audit series (Track 1's original mistake, vinu-screener item #18.4,
   vinu-stock-price item #19, and #7 below)**: there's no single
   blessed import path. `vinu_tools/__init__.py` exports nothing but
   `__version__`; a `get_indicator_module()` registry function exists
   (`compute/registry.py:149,157`) but even Track 1's own reference
   implementation (`signal_evidence/compute.py`) doesn't use it — 25+
   individual deep-path imports instead. If the correct usage pattern
   isn't used by the best-audited caller, it's unsurprising other
   components hand-rolled their own. Fix: document/enforce
   `get_indicator_module()` (or a `compute_indicator(name, rows)`
   wrapper) as the one blessed entry point, and add it to AGENTS.md's
   "How To Use" section (which currently covers alpha factors/bench/ML
   but never how to consume TA indicators).

### Other angles (beyond signal_evidence)

7. **A 4th confirmed instance of the duplication pattern**:
   `trend_lifecycle/compute.py:88-92` hand-rolls true range and ATR
   (`tr.rolling(14).mean()`) instead of importing `vinu-tools`' `atr`
   indicator — independently reproducing the exact same "SMA of TR" bug
   found in `vinu-tools`' own `atr.py` (finding #2 above).
8. **Checked and confirmed fine**: error handling/RunLog recording is
   centralized in `runner.py` (one shared try/except wrapping every
   angle's `compute()` call, already fixed from a previously-silent
   state per its own comment) and applies uniformly across all angles —
   not an inconsistency. No unresolved-bug TODOs found in a spot-check of
   8 other angles' compute.py files.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Given the direct connection to Decision 14, this is a
strong candidate to fix before Track 2 implementation begins.

**UPDATE (2026-09-26)**: **findings #1, #2, #3, and #7 are now built and
tested** — the real formula bugs, fixed exactly the way this item's own
concrete fix already specified, not re-derived.

- `vinu-tools/vinu_tools/compute/indicators/_shared/rolling.py`: new
  `wilder_smooth(values, period)`, extracted verbatim from `rsi.py`'s
  own already-correct recursion (`avg = (avg * (period - 1) + new) /
  period`, seeded by a plain average of the first `period` values) --
  copying it, not re-deriving Wilder's formula independently a second
  time. Unlike the `ema()` helper it sits beside, it has a real `None`
  warmup period (nothing before index `period - 1`) instead of
  fabricating a value from index 0.
- `atr.py` (finding #2): `sma(tr, period)` -> `wilder_smooth(tr,
  period)`. Directly relevant to Decision 14's 2xATR(14) move-detection
  floor -- this is now the ATR "2xATR" is normally understood to mean.
- `adx.py` (finding #1): `ema(tr/plus_dm/minus_dm, period)` ->
  `wilder_smooth(...)` for all three legs. Required more than a
  find-replace: `wilder_smooth` (unlike `ema`) returns real `None`
  during warmup, so `compute()`'s DI/DX math needed explicit `None`-
  handling it didn't need before (`ema()` never produced `None`) --
  handled explicitly (see the function's own inline comments), not
  papered over. The existing `period * 2` warmup cutoff for the exposed
  `adx_{period}` column is unchanged, verified still safe (the
  double-smoothed value is provably non-`None` by that index).
- **Finding #3 (0 of 2 tested)**: 14 new tests in
  `vinu-tools/tests/test_indicators.py` -- hand-computed known-value
  checks for `wilder_smooth` itself, a constant-true-range exact-value
  ATR check, a flat-market zero-ADX check, and a strong-uptrend
  ADX-toward-100 check. Exactly the "basic known-value test" this
  finding said would have caught both bugs.
- **Finding #7** (`trend_lifecycle`'s independent hand-rolled
  `tr.rolling(14).mean()`, the 4th confirmed duplication instance):
  fixed by importing the same shared `wilder_smooth` helper directly
  (`vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/
  compute.py`) rather than switching to the full indicator-registry API
  (a bigger, riskier change to this function's tightly-threaded
  pandas-Series calling convention than this finding asked for) --
  `dtype=float` on the resulting `pd.Series` converts `wilder_smooth`'s
  leading `None`s to `NaN` at the exact same first-valid index
  `rolling(14).mean()` already produced `NaN` for, so every downstream
  NaN-comparison keeps behaving exactly as it did before.
- Checked for blast radius before calling this done: grepped the whole
  monorepo for tests referencing `adx_14`/`atr_14` -- every other hit is
  a mocked HTTP fixture or a string field name, never a hardcoded
  expected numeric value from the old (buggy) formula, so the real
  fix carries zero cross-component regression risk.
- Confirmed zero regressions: full `vinu-tools` suite, 161 passed (up
  from 147, exactly +14), and `trend_lifecycle`'s own test files (7
  passed, unchanged) -- the rest of `vinu-initial-analysis`'s suite has
  pre-existing, unrelated collection errors (missing ML-library
  dependencies in this environment, confirmed by reading one directly:
  `ModuleNotFoundError: vinu_initial_analysis.angles.news_first_
  analysis`, nothing to do with this change).
- **What this item leaves open**: findings #4 (duplicated `_macd()`
  helper), #5 (mostly-unvectorized Python loops), and #6 (no enforced
  blessed import path, `AGENTS.md` not updated) are untouched --
  real, but lower-severity/more-invasive than the two formula bugs, not
  addressed in this pass.

**UPDATE (2026-09-26, later same day)**: re-verified findings #4 and #6
against current code before touching anything -- "check what's actually
implemented, not just claimed" -- and found #4 is now stale.

- **Finding #4 is already fixed, just not by this audit series**:
  `macd_signal/macd_signal.py` does `from
  vinu_tools.compute.indicators.macd.macd import _macd` -- a single
  `_macd()` definition (confirmed by grepping the whole package for
  `def _macd`: exactly one hit, in `macd.py`), not the independent
  copy-paste this finding described when it was written. Whatever
  fixed it happened outside this session and outside this audit's own
  tracked passes. No code change needed; recorded here so this finding
  stops showing as open when it isn't.
- **Finding #6, fixed as the finding's own text specified**: it asked
  for "document/enforce `get_indicator_module()` (or a
  `compute_indicator(name, rows)` wrapper) ... and add it to
  AGENTS.md's 'How To Use' section" -- and a search for that exact
  wrapper turned up one that already exists and already does more than
  the finding asked for: `vinu_tools/compute/registry.py`'s
  `apply_indicators(rows, names)`, which merges one or many computed
  indicator (or alpha101/158/360 recipe) columns straight onto row
  dicts, already tested (`tests/test_compute_registry.py`,
  `tests/test_indicators.py`), already used internally
  (`vinu_tools/engine/engine.py`) -- just never documented as the
  blessed path or referenced from `AGENTS.md`. Fix: added a "Compute a
  TA indicator" subsection to `vinu-tools/AGENTS.md`'s "How To Use"
  section naming `apply_indicators()` as the entry point, explicitly
  telling future callers not to deep-import
  `vinu_tools.compute.indicators.<kind>.<kind>`, and naming
  `signal_evidence/compute.py`'s 24 deep-path imports as the pattern to
  not repeat -- with a one-line explanation of why: those are exactly
  the imports that let the ADX/ATR/`trend_lifecycle` formula bugs
  (findings #1/#2/#7 above) go unnoticed, since nothing forced a
  hand-rolled caller through the one place a fix or a test would
  actually reach.
  - **Deliberately not done**: rewriting `signal_evidence/compute.py`'s
    24 imports to call `apply_indicators()` instead. That's a bigger,
    riskier refactor than finding #6 itself asked for (document +
    enforce going forward, not retrofit every existing caller) --
    same reasoning already applied to finding #7's `trend_lifecycle`
    fix, which reused `wilder_smooth` directly rather than switching to
    the full registry API for the same reason. Left open as a separate,
    optional cleanup.
  - Documentation-only change; no test suite to re-run (AGENTS.md is
    not executable), so no pass/fail count applies here.
- **What this item leaves open now**: only finding #5 (mostly-
  unvectorized Python loops) remains untouched -- a real but
  significantly larger, performance-only change, not attempted in this
  pass.

**UPDATE (2026-09-27)**: **finding #5 scoped into a concrete plan, deferred
by explicit instruction** ("put as the plan, we will do it later" — not
a request to implement now). Checked the real scope before writing this
down rather than guessing: 18 of the ~28 indicator modules use a Python
`for`/`range` loop, not just `mfi.py` (the finding's own named example)
— `accumulation_distribution_line`, `adx`, `aroon`, `bollinger`, `cci`,
`chaikin_money_flow`, `daily_return`, `ichimoku`, `macd`, `mfi`,
`momentum_n`, `obv`, `parabolic_sar`, `roc`, `rsi`, `stochastic`,
`supertrend`, `williams_r`.

**Planned approach, for whenever this gets picked up**:
1. **Split the 18 into two buckets first, before touching any code** —
   this is the actual scoping work, not a detail to skip. Bucket A:
   rolling-window aggregates with no path dependency (`bollinger`, `cci`,
   `stochastic`, `williams_r`, `chaikin_money_flow`, `roc`,
   `momentum_n`, `daily_return`, `accumulation_distribution_line`,
   `aroon`) — these are the safer, more mechanical vectorization
   candidates, likely a `.rolling()`/`.ewm()` swap each. Bucket B:
   recursive/path-dependent smoothing (`adx`, `rsi`, `macd`, `obv`,
   `mfi`, `parabolic_sar`, `supertrend`, `ichimoku`) — vectorizing these
   correctly (without silently changing the numeric output) is
   genuinely harder and higher-risk.
2. **Bucket B carries the real risk this plan needs to name explicitly**:
   item #21 pattern #2 already found that `trend_lifecycle/snapshots.py`
   persists indicator values into a KNN pattern-matching library whose
   own docstring demands they "stay directly comparable forever" — any
   vectorized rewrite of a Bucket B indicator must be checked against
   every known persisted-comparability consumer first (not just this one
   already-found instance; a fresh grep for other persisted-feature
   consumers of these indicators is part of the work, not an
   afterthought), or it risks silently invalidating historical data the
   same way a formula change would.
3. **Verification convention already established this session, reuse
   it**: before switching any indicator's implementation, compute the
   old and new implementations side-by-side on the same fixture data and
   assert index-for-index numeric equality (the exact check already used
   for `trend_lifecycle`'s `true_range`/`wilder_smooth` switch,
   item #21 pattern #2) — a passing test suite alone would not catch a
   subtly-different-but-still-plausible vectorized formula.
4. **Sequencing**: Bucket A first (lower risk, faster win), Bucket B
   only after a real persisted-comparability audit per indicator, one
   indicator at a time — not a single big-bang rewrite of all 18.
- No code changed in this pass — this is a plan for a future session,
  not an implementation.

## 21. Cross-cutting patterns, found by synthesizing across items 1-20 — not new audits, connections between existing ones

Asked directly whether items were being cross-referenced against each
other, not just recorded in isolation. They are — this item is that
synthesis pass made explicit, pulling out patterns that only become
visible by comparing multiple, unrelated audits against each other.

1. **No service anywhere has server-side point-in-time enforcement — a
   systemic gap, not isolated incidents.** Item #19 found this
   independently for both `vinu-stock-price` and `vinu-news` — as-of
   clamping exists *only* in `vinu-agent`'s tool code, with zero
   server-side safety net on either data provider. Combined with item
   #11.2 (those same client-side clamps are themselves untested), the
   real picture is: the single property this entire design depends on
   most — no look-ahead bias — is currently enforced nowhere except
   caller discipline, unverified by any test, at the two places raw data
   enters the whole system. This is more serious stated as one system-
   wide gap than as two separate per-service findings. Fix direction: a
   shared `as_of`-enforcing pattern (decorator or middleware) built once
   in `vinu-infra` and required on every data-serving endpoint, not left
   to each service to remember independently.
2. **Duplicated indicator/computation logic is now a confirmed pattern,
   not a one-off mistake — 4 independent instances, one root cause.**
   Track 1's original hand-rolled ADX/RSI
   (`06-mistake-duplicated-indicator-logic.md`), `vinu-screener`'s
   `operators.py` (item #18.4), `vinu-stock-price`'s `query/indicators.py`
   (item #19), and `trend_lifecycle`'s hand-rolled ATR (item #20.7) are
   four separate components independently reimplementing the same math
   `vinu-tools` already provides correctly (or, for ADX/ATR, provides
   *incorrectly* — item #20.1-2). Item #20.6 identified the likely root
   cause directly: there is no single blessed import path, and even
   Track 1's own reference implementation doesn't use the registry
   function that exists for this. Four independent teams/sessions making
   the same mistake points at the shared entry point being undiscoverable,
   not at four unrelated lapses in judgment.

   **UPDATE (2026-09-26)**: `trend_lifecycle`'s instance is now *partly*
   closed, not fully -- worth being precise about which half. Item #20's
   own fix made `wilder_smooth` a real shared helper and `trend_lifecycle/
   compute.py` now imports and calls it directly instead of hand-rolling
   its own (buggy) smoothing math -- the actual formula bug this
   component reproduced is gone. But the true-range computation itself
   (`high - low` / `abs(high - prev_close)` / `abs(low - prev_close)`)
   is still computed inline here, not via `vinu-tools`' own
   `true_range()`/full `atr` indicator module -- a smaller, still-real
   duplication of a much simpler piece of math, not touched. Track 1's
   original instance, `vinu-screener`'s `operators.py`, and
   `vinu-stock-price`'s `query/indicators.py` (the other 3 of 4) are
   entirely untouched. Item #20.6's actual root-cause fix (enforcing
   `get_indicator_module()` as the one blessed path, documenting it in
   `AGENTS.md`) remains unbuilt -- this update fixed instances of the
   *symptom* (wrong formula), not the *cause* (no discoverable shared
   entry point) this finding says is the real root.
3. **"Compute why something failed, then discard it before persisting" —
   a recurring habit across at least three unrelated components.** Sweep
   candidates' ranking verdict (item #3), the research loop's
   generation-time candidate scoring (item #16.2), and the screener's
   per-symbol reject reasons (item #18.3) are three structurally
   identical gaps in three components that have nothing else to do with
   each other: each one computes a real, specific reason something was
   rejected, and none of them persist it. This is the same shape as
   pattern #2 — independent components converging on the same omission —
   which suggests a shared "rejection audit trail" utility (log a
   structured reason wherever a candidate/symbol/run gets cut) would fix
   three items at once if built as one reusable piece in `vinu-infra`,
   rather than three separate one-off schema additions.
   **Concrete shared shape, so this is buildable as one piece rather than
   re-derived three times**: a single `RejectionRecord` shape (a
   `vinu_infra` helper, not a new SQL table per component — different
   components can each store rows in their own existing storage, but all
   through the same write function/schema): `{entity_type: "sweep_run" |
   "generation_candidate" | "screener_symbol", entity_id: str,
   stage: str, rejection_category: str, rejection_detail: str,
   compared_against_id: str | None, timestamp: str}`. `entity_type` +
   `entity_id` says what got rejected; `stage` says at which step
   (matches each component's own existing stage names — no renaming
   needed); `rejection_category` is the same kind of categorized reason
   already sketched in item #14 (`"worse_sharpe"`,
   `"failed_pbo_gate"`, etc. — generalized beyond sweeps to any
   rejection); `compared_against_id` links to the winner/survivor where
   one exists (the sweep's winning run, the chosen generation candidate,
   nothing for a screener symbol, which has no single "winner"). One
   `vinu_infra.rejection_log.record_rejection(...)` function, called from
   all three existing components at the exact point each one already
   computes (and currently discards) its own reason.
4. **A shared resilience helper exists and is mostly used correctly — but
   `yfinance` bypasses it in two unrelated places.** `vinu-agent`'s
   `fundamentals_tool.py` (item #11.3) and `vinu-stock-price`'s
   `providers/yfinance.py` (item #19) both skip the shared
   `vinu_infra.retry` helper that every *other* provider/tool in both
   codebases correctly uses. Not a systemic gap like #1/#2/#3 — the
   pattern here is narrower and specific to one flaky vendor integration
   touched by two different teams, both forgetting the same shared tool.
5. **Evidence fragmentation, already named explicitly in
   `01-full-system-layer-map.md`, restated here for completeness**:
   Track 1's `signal_evidence` data, the research loop's generation-time
   evidence, and `vinu-reflection`'s continuous findings are three
   separate evidence streams, none feeding the `HypothesisRegistry`
   already built to consume exactly this kind of data (items #1, #16.1,
   and the layer-map file's dedicated section).

**Why this item matters on its own**: patterns 1-3 each look like a
single fixable gap when found once, but recur 3-4 times independently
across completely unrelated components. That repetition is itself
evidence that the fix belongs at the shared-infrastructure level
(`vinu-infra`), not as N separate patches applied once per component —
the same lesson `06-mistake-duplicated-indicator-logic.md` already
taught once for indicators specifically, now generalizing to point-in-time
enforcement and rejection-reason recording as well.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed.

**UPDATE (2026-09-26)**: pattern #3 ("compute why something failed, then
discard it") gained a **fourth confirmed instance**, found and fixed
while building `reverse-engineering/`'s live-decision loop:
`live_decision_agent`'s real, evidence-grounded verdict was being
computed, returned over HTTP, and only logged — never persisted. Fixed
with `vinu-live/vinu_live/live_decision/schema.py`'s `LiveDecisionRecord`
+ the `live_decisions` table (see `reverse-engineering/
02-implementation-status.md`'s 2026-09-26 entry). This is the same
shape as items #3/#16.2/#18.3, now a fourth data point for the pattern,
not a coincidence — but it does **not** resolve those three original
items, and the shared `vinu_infra.rejection_log.record_rejection(...)`
utility this section recommends is still not built. Each of the four
instances (three original + this one) still has its own one-off fix,
which is exactly the "N separate patches instead of one shared piece"
outcome this item's own closing paragraph warned would happen without
the shared infra-level fix.

**UPDATE (2026-09-26, later same day)**: **pattern #1 (no service
anywhere had server-side point-in-time enforcement) is now fixed** —
built as this item's own recommended shared piece, not two separate
per-service patches, for the first time one of these three recurring
patterns got the shared-infra-level fix rather than another one-off.

- New `vinu_infra/point_in_time.py::clamp_to_as_of()`, wired into
  vinu-stock-price's `/candles/{symbol}` (item #19 finding #1, the
  "HIGH"-severity one) and vinu-news's `/ticker/{symbol}` (item #19
  finding #2) — see item #19's own dated update above for the full
  detail, tests, and confirmed-zero-regressions numbers.
- **Deliberately not a decorator/middleware**: pattern #1's own fix
  direction offered "a shared `as_of`-enforcing pattern (decorator or
  middleware)" as one option. A plain shared function, called explicitly
  at each affected route, was chosen instead — the two services' route
  signatures already differ (and every *other* read route in each
  service differs yet again), so a generic wrapper would need to
  special-case each shape anyway; a function call gets the same
  "no per-service reinvention" result with far less framework-level risk
  than threading a new decorator through two independent FastAPI apps
  blind to each route's exact existing parameter contract.
- **What pattern #1 leaves open**: only the two routes closest to a
  direct fit were wired (both already had an absolute `to`/`from`-style
  shape). Every other read route in both services is a relative
  `days`/`hours`-back-from-now window with no absolute end parameter at
  all — extending `as_of` there means first deciding how it interacts
  with each route's own relative-window semantics, a real design
  decision not made here. Item #11.2's ask to test vinu-agent's own
  client-side clamps is unaffected by this fix (that's now a second
  layer of defense, not the only one, but still itself untested).
  Patterns #2 (indicator duplication) and #3 (silent rejection-reason
  discard) still have no shared-infra-level fix — each of their
  confirmed instances still carries its own one-off patch, exactly the
  outcome this item's own closing paragraph warned would happen.

**UPDATE (2026-09-26, later same day)**: **pattern #3 now has its
shared-infra-level fix** — `vinu_infra/rejection_log.py`'s
`RejectionRecord`/`record_rejection()`, built exactly to the concrete
shape this section's own text already specified, and wired into its
first real consumer.

- Item #18 finding #3 (the screener's per-symbol reject reasons) is the
  first of the pattern's instances to actually adopt the shared shape —
  see that item's own dated update above for the full fix, including a
  second, independent gap it turned up (`RankerSnapshot.to_dict()` never
  serialized `trace` at all, despite it already reaching the store).
- **Deliberately not done in the same pass**: wiring the other two
  original instances (item #3's sweep comparison verdict, item #16.2's
  generation-time candidate scoring) onto this same shape. Item #3
  already has an existing persistence surface to extend (a sweep-run
  results table); item #16.2 has none at all yet — deciding where
  generation-time rejections should live, how they're queried, and
  their retention is a real, separate design question the shared shape
  itself doesn't answer, not a mechanical wiring job the way the
  screener instance was. The 4th instance found while building
  `reverse-engineering/` (`live_decision_agent`'s verdict) already has
  its own working fix (`LiveDecisionRecord`) and wasn't retrofitted onto
  this shape either, for the same "don't touch something that already
  works for a purely stylistic consistency win" reasoning.
- Pattern #2 (indicator duplication) still has no shared-infra-level
  fix, and now has a partial 5th instance closed the same "check each
  claim individually" way pattern #3's screener instance was investigated
  — see item #18 finding #4's own dated update.

**UPDATE (2026-09-27)**: item #20 finding #7's own remaining gap
(`trend_lifecycle/compute.py`'s hand-rolled true-range formula, distinct
from the smoothing-method bug that finding already fixed) is now closed
— and investigating it surfaced a **6th, more serious duplication
instance in the same angle**, deliberately left unfixed for a real
reason, not an oversight.

- `trend_lifecycle/compute.py`'s peak-detection ATR used to compute true
  range inline (`pd.concat([high-low, ...], axis=1).max(axis=1)`) before
  handing it to the already-shared `wilder_smooth()` finding #7 wired in
  earlier. Verified index-for-index identical to `vinu_tools`' own
  shared `true_range()` helper on a random 40-bar series (max
  difference `0.0`) before switching, not assumed — same formula, this
  was pure duplicated code, not a numeric bug. Now calls `true_range()`
  directly. 1 new regression-guard test in `test_trend_lifecycle.py`.
  Confirmed zero regressions: `test_trend_lifecycle.py` +
  `test_trend_lifecycle_backtest.py` 8 passed (up from 7, exactly +1).
- **While tracing "same definition as snapshots" (this module's own
  comment) to check whether a second copy existed there too — it did,
  and it's substantially worse.** `trend_lifecycle/snapshots.py`'s
  `_compute_all_indicators()` is an entirely separate, ~90-line
  hand-rolled indicator library (its own RSI, MACD, ATR, ADX, CCI,
  Williams %R, Stochastic) that was never covered by item #20's original
  audit pass at all. Its own RSI (`_compute_rsi`: plain
  `rolling(period).mean()` for both gain and loss averages) and ADX
  (`.ewm(alpha=1/period, adjust=False)`, seeded from bar 0) reproduce
  the exact same wrong-smoothing-convention bug class findings #1/#2
  fixed once already in `vinu-tools`' own `adx.py`/`atr.py` — real,
  confirmed formula divergences from `vinu_tools`, not just duplicated
  code.
- **Deliberately NOT fixed, for a reason specific to this file, not
  found in any of the other 5 instances**: this module's own docstring
  states its design invariant directly — "every column uses FIXED
  periods that never change... this guarantees Peak_A and Peak_B are
  directly comparable forever." `patterns.py`'s `build_feature_matrix()`
  confirms this isn't rhetorical: `rsi_14`/`rsi_7`/`atr_14` (via a
  derived `atr_pct`) are persisted feature-matrix columns a live KNN
  pattern-match compares a NEW snapshot against an already-stored
  historical library on. Changing these formulas would silently change
  what "similar" means between an old, already-stored pattern (computed
  with the current formula) and every new one going forward (computed
  with a corrected formula) — corrupting the exact cross-time
  comparability this file's own docstring names as its core guarantee.
  Every other duplication instance fixed in this audit series (screener,
  vinu-tools itself, this same file's own true-range fix above) recomputes
  its indicator fresh on every call, with nothing persisted for later
  cross-time comparison — this is the first instance found where that
  isn't true, and it changes the right answer from "fix it" to "this
  needs someone to decide a migration story first" (recompute and
  accept a one-time break in the historical library's comparability,
  version-tag old vs. new rows and compare only within a version, or
  leave the current formulas as the library's permanent, de facto
  definition). Not decided here — a real design/data-migration
  question, not a wiring gap, and a materially different kind of risk
  than every other instance of this pattern found so far.

## 22. vinu-strategy audit (2026-09-25) — Layer 4, includes a real silent-degraded-weights risk

Real, verified findings for the weight-computation layer that runs an
already-validated strategy day to day.

### Process/logic design issues

1. **Silent degraded weights on upstream failure — the most serious
   finding in this item.** `clients/base.py:40-56`'s `BaseClient._request`
   catches every failure class (timeout, connect error, 4xx/5xx, generic
   exception) and returns `{}` at warning/error log level — it never
   raises. `service.py:82-83` and `_fetch_correlation_for_symbol`/
   `_fetch_angles_for_symbol` (168-214) treat that `{}` as "no data for
   this symbol," defaulting features to 0.0 and correlation/angle context
   to empty. Result: if `vinu-research` or the features service is down,
   the strategy run **succeeds anyway** and produces real weights
   computed as if every indicator were absent — nothing in
   `StrategyResult` flags the run as degraded. A genuine infrastructure
   outage produces output that looks completely normal downstream. Fix:
   propagate a per-symbol/per-source "data missing" flag into
   `signal_context`, and fail or mark the result degraded when required
   fields are absent for a nontrivial fraction of the universe.
   **Concrete field**: `data_quality: {symbol: {missing_sources:
   ["correlation" | "angles" | "features"], is_degraded: bool}}` attached
   to `StrategyResult` (`models/strategy.py`) alongside the existing
   `weights`/`rule_trace` fields, populated wherever `BaseClient._request`
   currently returns `{}` (`clients/base.py:40-56`) instead of that
   result being silently absorbed into a 0.0 default.
2. **Zero weight validation anywhere, for any risk method.**
   `engine/risk.py:83-87`'s `risk_none` returns weights completely
   unmodified, and no stage anywhere in `pipeline.py`/`service.py`
   checks for NaN/inf or a valid sum/range, regardless of which risk
   method is chosen. `evaluate_expression`
   (`engine/expression.py:83-84`) returns `nan` on division by zero
   rather than erroring — that `nan` flows unchecked through allocation →
   timing → risk → storage. Fix: add a final sanity-check step in
   `WeightPipeline.run` (finite values, `allow_short` invariant enforced)
   regardless of the chosen risk method.
3. **Point-in-time safety is fully delegated upstream, with no
   verification at this layer.** `allocate_signal_scaled`
   (`engine/allocation.py:18-45`) scales by the single most-recent
   feature snapshot passed in, with no timestamp check anywhere in
   `service.py`/`features_client.py` confirming that snapshot is actually
   as-of-decision-time. `engine/timing.py` does no rolling/lookback math
   itself either (confirmed: no rolling/window/ewm/shift patterns found)
   — both stages simply trust whatever `vinu-tools`/`vinu-research` hand
   them, with no independent check at this layer.
4. **Confirmed directly relevant to `03-strategy-definition-full-schema.md`**:
   the proposed `must_conditions`/`risk_management`/precondition-
   postcondition fields would do **nothing** if just added as dataclass
   fields on `StrategyConfig`. `models/strategy.py:17-29` hardcodes
   `_KNOWN_PIPELINE_KEYS = {selection, allocation, timing, risk}`, and
   `pipeline.py`'s `WeightPipeline.run` calls exactly those 4 stages in a
   fixed sequence (lines 41-56) — it would never read new fields. Real
   work needed to actually wire that schema in: a new stage type in
   `PipelineConfig`, a new `run_x` dispatcher module (mirroring
   selection/allocation/timing/risk), and a call site inserted into the
   pipeline sequence. Worth knowing *before* committing to an
   implementation plan for item #07's schema, not after.
5. **A small, real bug**: `engine/risk.py:116-119`'s `RISK_METHODS`
   includes a working `"shock_aware"` method, but
   `models/strategy.py:28`'s `_KNOWN_METHODS["risk"]` only lists
   `{"normalize", "none"}` — any strategy using `shock_aware` logs a false
   "unknown risk method" warning at load time despite working correctly
   at runtime. Fix: add `"shock_aware"` to the known-methods set.

### Code-level issues

6. **Registry reload is not atomic.** `engine/registry.py:19-23,46-47`'s
   `load_all()` clears `self._strategies` then repopulates it
   entry-by-entry with no lock — a reload triggered while requests are in
   flight can return `None` for a strategy that exists but hasn't been
   re-added yet mid-reload. Fix: build the new dict in a local variable,
   assign it in one atomic swap.
7. **The 10-worker thread pool buys almost nothing.**
   `clients/base.py:26-27,34-35`'s shared `self._lock` wraps every HTTP
   call for its full round-trip, and both `FeaturesClient`/
   `CorrelationClient` are single instances shared across
   `service.py`'s `_MAX_WORKERS=10` executor — concurrent symbol fetches
   are effectively serialized through one call at a time regardless of
   the thread pool. Fix: drop the lock (httpx.Client is thread-safe for
   concurrent requests) or use one client per worker.
8. **No test coverage for `engine/timing.py`** — the only stage that can
   materially rewrite weights *after* allocation has zero tests (test
   directory covers allocation/pipeline/risk/selection/registry/
   rules_engine/expression, but not timing).

**Checked and confirmed clean, a 6th non-instance of the recurring
duplication pattern (items #2/#18.4/#19/#20.7)**: `engine/` has zero
imports of `vinu_tools` and no hand-rolled indicator math —
`expression.py` only does arithmetic over numbers already computed
elsewhere. This layer correctly consumes rather than recomputes.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Given real trading weights could be silently produced from
degraded data, finding #1 is a strong candidate to prioritize.

**UPDATE (2026-09-26)**: **findings #1 and #5 are now built and tested.**

- **Finding #1**, the most serious in this item, built exactly to its
  own concrete field spec: `StrategyResult` (`models/strategy.py`) gained
  `data_quality: {symbol: {missing_sources: [...], is_degraded: bool}}`.
  New `StrategyService._compute_data_quality` (`service.py`) checks, per
  symbol, whether each source the strategy actually *required*
  (`features_required`/`correlation_required`/`angles_required`) came
  back with real data -- sparse, only symbols missing something appear at
  all. **Deliberately "mark," not "fail"** (the finding offered both):
  raising mid-`evaluate()` would be a new failure mode that could break
  existing scheduled callers in ways nobody asked for; marking the
  result surfaces the exact problem (a genuine infra outage no longer
  looks identical to "this symbol legitimately has no signal") without
  changing anything about who else calls this method or how. Also logs a
  `WARNING` with the missing-source breakdown when any symbol is
  degraded, and `StrategyAPI.evaluate()` exposes `data_quality` in the
  HTTP response (sparse, `{}` omitted, same convention `rule_trace`
  already uses).
- **Finding #5** (a small, real bug, fixed in the same pass since it's
  the same file): `"shock_aware"` added to `_KNOWN_METHODS["risk"]` --
  `engine/risk.py`'s own `RISK_METHODS` already had a working
  `risk_shock_aware`; any strategy using it logged a false "unknown risk
  method" warning at load time despite working correctly.
- **10 new tests**, all passing: 8 in new `test_data_quality.py`
  (7 unit-level against the static `_compute_data_quality` helper
  directly, 1 end-to-end through the real `evaluate()` path with a
  lightweight `__new__`-constructed service, same pattern
  `test_reduce_angle.py` already uses to avoid standing up a full
  registry/storage/client stack), 2 in `test_pipeline.py`
  (`TestShockAwareIsAKnownRiskMethod` -- one confirming the false warning
  is gone, one confirming a genuinely unknown method still warns, so the
  fix didn't just suppress the warning path entirely). Confirmed zero
  regressions: full `vinu-strategy` suite, 93 passed (up from 83, exactly
  +10).
- **What this item leaves open**: finding #3 (point-in-time safety fully
  delegated upstream with no verification at this layer), #4 (the
  proposed `must_conditions`/`risk_management` schema fields would need
  real pipeline-dispatcher wiring, not just dataclass fields, to do
  anything), and the code-level findings (#6 non-atomic registry reload,
  #7 one-client-per-thread-pool concurrency question, #8 no test coverage
  for `engine/timing.py`) are all untouched.

**UPDATE (2026-09-26, later same day)**: **finding #2 is now also
built and tested** — a single, method-agnostic final gate, built exactly
as this finding's own fix specified: "add a final sanity-check step in
`WeightPipeline.run` (finite values, `allow_short` invariant enforced)
regardless of the chosen risk method."

- `engine/pipeline.py`: new `WeightPipeline._sanitize_weights`, called
  once at the end of `run()` on whatever `final_weights` any
  `RISK_METHODS` entry produced -- including `risk_none()`, which passes
  weights through completely unmodified and was the clearest concrete
  case this gap could bite on. Non-finite weights (the real, demonstrated
  path: `evaluate_expression`'s `except ZeroDivisionError: return
  float("nan")`) are dropped outright; a negative weight when the
  strategy's own `allow_short=False` is set gets clamped to `0.0` rather
  than dropped, so the symbol stays visible in the result at its correct
  (zero) exposure instead of silently vanishing.
- **Checked the surrounding wiring before calling it done, not just the
  computation itself** -- and found a real instance of exactly the
  pattern item #21.3 already names three times over: `pipeline.run()`
  put `sanity_issues` into its own internal `meta` dict, but
  `StrategyService.evaluate()` never read it back out into anything a
  caller could see (same gap `data_quality`, above, closed for the
  upstream-failure case one entry earlier in this same file). Fixed the
  same way: `StrategyResult` (`models/strategy.py`) gained a real
  `sanity_issues` field, `service.py`'s `evaluate()` threads it through
  from `pipeline_meta`, and `StrategyAPI.evaluate()` exposes it in the
  HTTP response (sparse, same convention as `rule_trace`/`data_quality`).
  The pipeline layer's own existing warning log was kept as the one
  place this gets logged (not duplicated in `service.py` too) --
  `service.py`'s fix is specifically about making the *value* reachable,
  not re-logging something already logged correctly.
- **9 new tests**, all passing: `TestSanitizeWeights` (6, unit-level),
  `TestWeightPipelineAppliesTheSanityGateRegardlessOfRiskMethod` (2,
  proving the gate runs inside the real `run()` call and specifically
  catches a NaN surviving `risk_none`'s own pass-through), and
  `TestSanityIssuesReachTheRealStrategyResult` (1, proving the value
  actually reaches `StrategyResult` through the real `evaluate()` call
  chain, not just `pipeline.run()` in isolation). Confirmed zero
  regressions: full `vinu-strategy` suite, 102 passed (up from 93, +9).

**UPDATE (2026-09-26, third pass same day)**: **findings #6 and #8 are
now also built and tested**, both exactly as this item's own fix text
specified.

- **Finding #6** (`engine/registry.py`'s `load_all()` not atomic): fixed
  exactly as specified -- "build the new dict in a local variable, assign
  it in one atomic swap." The loop now populates a local `loaded` dict;
  `self._strategies = loaded` happens once, after the loop (and on the
  early "dir doesn't exist" return too, so that path can't leave a stale
  dict from a prior successful load lying around under a new,
  since-deleted directory). New test
  (`test_registry.py::test_reload_is_atomic_not_visible_partially_
  repopulated`) proves the property directly rather than trusting the
  diff: it spies on `StrategyConfig.from_dict` (called once per yaml file
  inside the loop) and asserts `registry._strategies` is still exactly
  the pre-reload snapshot on every single call -- i.e. the real internal
  dict is provably untouched until the loop finishes, not just "probably
  fine because the diff looks right."
- **Finding #8** (`engine/timing.py` had zero tests, the only stage that
  can rewrite weights *after* allocation): new `tests/test_timing.py`,
  10 tests covering `timing_none` (pass-through), `timing_rules`
  (no-rules no-op, a fired rule adjusting only the matching symbol, a
  symbol entirely absent from `signal_context` not crashing, multiple
  rules chaining in order -- `(1.0 + 0.5) * 2.0 == 3.0`, proving order
  and compounding, not just independent application), and `run_timing`'s
  dispatch (`none`, `rules`, and the unknown-method warning fallback).
  One assumption caught and fixed while writing these, not after: a rule
  that evaluates but doesn't fire for a given symbol still produces a
  non-empty trace entry (`{"fired": False, ...}`) -- `timing_rules`'s own
  `if sym_trace:` check is about the list being non-empty, not about
  whether anything in it fired, so a first draft asserting "no trace for
  a symbol the rule didn't fire on" was itself wrong and was corrected
  to assert `trace[sym][0]["fired"] is False` instead of symbol absence.
- Confirmed zero regressions: full `vinu-strategy` suite, 113 passed (up
  from 102, +11 -- 1 registry test + 10 timing tests).
- **What this item leaves open now**: finding #3 (point-in-time safety,
  an upstream design question, not invented here) and #4 (the schema
  fields need real pipeline-dispatcher wiring -- a bigger implementation
  decision, not attempted in this pass) remain untouched.

**UPDATE (2026-09-26, later same day)**: **finding #7 is now built and
tested** — the `httpx.Client` thread-safety question decided (httpx
documents its own client as thread-safe for concurrent requests, its
internal connection pool handles this), not left open.

- `clients/base.py`'s `BaseClient` had a `threading.Lock()` wrapping
  `_request()`'s *entire* network round-trip -- with `FeaturesClient`/
  `CorrelationClient` each a single instance shared across `service.py`'s
  `_MAX_WORKERS=10` executor, every concurrent symbol fetch was
  serialized through one call at a time regardless of the thread pool,
  buying almost nothing from the concurrency it looked like it enabled.
  Dropped the lock entirely (the finding's first option) rather than
  switching to one client per worker (its second) -- a single shared
  client's pooled connections are strictly more resource-efficient than
  10 separate pools against the same upstream service, and nothing else
  in this class touches shared mutable state that the lock was also
  incidentally protecting.
- 9 new tests in a new `tests/test_base_client.py` (this file had zero
  coverage before): the existing retry/backoff/error-handling behavior
  confirmed unchanged (success, transient-status retry-then-succeed,
  retries exhausted, timeout retry, non-transient HTTP error with no
  retry, an unexpected exception), plus the actual property this fix
  buys — 5 threads issuing a mocked 0.2s-sleep request concurrently
  complete in roughly one sleep duration, not five (a generous ceiling
  below the old serialized total, avoiding flakiness on a loaded box
  while still failing hard if the lock ever comes back) — and a direct
  regression guard that `_lock` no longer exists on the instance at all.
  Confirmed zero regressions: full `vinu-strategy` suite, 122 passed (up
  from 113, exactly +9).
- **What this item leaves open now**: findings #3 and #4 remain
  untouched, as noted above.

## 23. vinu-portfolio audit (2026-09-25) — Layer 5, includes circuit breakers that mostly don't enforce anything

Real, verified findings. Two of the four process/logic items describe
risk controls that look real (computed, tested, documented) but are
never actually acted on — a structurally serious finding for a component
whose entire job is portfolio-level risk protection.

### Process/logic design issues

1. **No same-symbol conflict/netting policy across strategies.**
   `service.py`'s `allocate_risk_parity` (286-365) and
   `compute_daily_allocation` (760-946) allocate weight per *strategy
   name*, never aggregated by *symbol*. If Strategy A wants +weight on
   AAPL and Strategy B wants -weight on the same AAPL, both flow through
   independently with their own `target_weight`/`position_size` — zero
   netting, zero conflict detection, not even a flag (grepped for
   "net"/"opposite"/"conflict": nothing relevant). `_check_composition_gaps`
   (463-498) only checks single-strategy concentration and pairwise
   correlation — never opposite-direction same-symbol cases. No test
   covers this. Fix: add an explicit symbol-level netting/flagging step
   before weights leave `compute_daily_allocation`.
   **Concrete mechanism, and an explicit open decision the user should
   make deliberately, the same way Decision 14 was made rather than
   defaulted**: a `SymbolConflict` shape —
   `{symbol, contributions: [{strategy_name, direction, weight}],
   net_weight, policy_applied: "net" | "kept_separate" | "blocked"}`,
   computed as a new step in `compute_daily_allocation` right after
   per-strategy weights are gathered, before they leave the function.
   The open policy question this surfaces (not yet decided, and
   genuinely the user's call, not a default to assume): should opposing
   positions on the same symbol be (a) **netted** into one final position
   (simplest, but hides that two strategies actively disagree), (b)
   **kept separate** and handed to Layer 6 as two distinct legs (more
   transparent, but `vinu-live`'s `signal_translator.py` would need to
   handle two `OrderInstruction`s for the same symbol, which it isn't
   currently built to expect), or (c) **blocked/flagged** for manual
   review above some conflict-size threshold. This needs a real decision,
   not a guess.
2. **The circuit breaker's "halve"/"flat" actions are computed but never
   enforced — only "halt" does anything.**
   `PortfolioDrawdownMonitor.update()` (`circuit_breakers.py:99-117`)
   computes a 4-state `action` field (ok/halve/flat/halt); only `halt`
   calls `_halt_trading()` (line 119), which POSTs to `/broker/halt`.
   The docstring itself says "orchestrator halves size at halve, exits to
   flat at flat" — but no orchestrator anywhere in this codebase (grep
   confirmed) actually consumes `halve`/`flat` to reduce sizing. They're
   values in a dict nothing reads. Fix: wire `halve`/`flat` into
   `compute_daily_allocation`'s sizing multiplier, or explicitly
   document/rename them as advisory-only so they're never mistaken for
   real controls.
3. **A second, apparently-inert risk-tiering system.** `risk_budget.py`'s
   `compute_risk_budget` (131-212) computes per-symbol `tier`/`halted`/
   `suggested_size_multiplier`, exposed only via `GET /risk/status`
   (`server/app.py:64-66`) — a fully separate call path from
   `compute_daily_allocation`/`apply_position_sizing`. Nothing in this
   codebase reads `/risk/status`'s output back into actual position
   sizing. Unless an external consumer (checked: not found in
   `vinu-agent`) polls and enforces it, this is a second circuit breaker
   that exists in name and API only. Fix: confirm a real enforcement
   consumer exists; if not, this needs the same wiring as finding #2.

   **Concrete mechanism for both #2 and #3 together, and a direct
   connection back to item #14's `CompositeSizer` that should have been
   made immediately rather than found on a second pass**: both findings
   are the exact same shape of gap item #14 already named for
   `vinu-simulator`'s backtesting side — real risk signals exist
   (drawdown state, risk tier) but nothing composes them into final
   sizing. The fix here is the *live-side* counterpart of the same idea:
   `compute_daily_allocation` should read both
   `PortfolioDrawdownMonitor.action` and `risk_budget`'s per-symbol
   `suggested_size_multiplier` as two more multiplicative factors,
   applied the same way sizing already gets scaled, before final weights
   are returned — not a new mechanism, but finally consuming two real
   signals that already exist and are already computed. This means
   `CompositeSizer` isn't only a `vinu-simulator` backtest concept — it's
   the same missing piece on both sides of the backtest/live boundary,
   worth remembering so it gets built once and shared, not designed
   twice independently for simulator and portfolio.
4. **Drawdown protection goes silently inert if the agent API is
   unreachable — no fail-safe, no escalation.**
   `drawdown_scheduler.py:27-50`'s `run_once()` catches any exception
   reaching `/agent/broker/account`, logs a `WARNING`, and returns
   `{"status": "unavailable"}` — the monitor's peak/start state simply
   doesn't advance that cycle, with no retry/backoff and no
   alert-escalation path. If the agent API stays down for an extended
   period, real drawdown protection is completely inert with nothing but
   an easily-missed log line marking it. Fix: treat N consecutive
   `unavailable` cycles as itself an alertable/haltable condition.
   **Concrete mechanism**: add `consecutive_unavailable_count: int` to
   `PortfolioDrawdownMonitor`'s own state, incremented each time
   `run_once()` returns `{"status": "unavailable"}` and reset to 0 on any
   successful update; once it crosses a threshold (e.g. 3 consecutive
   cycles — a guessed starting constant, same posture as
   `FORWARD_HORIZON_BARS`/`floor_multiple` elsewhere in this file, meant
   to be revisited once real data exists), treat it as its own `action:
   "halt"` state — "we don't know the drawdown, so trade as if it might
   already be breached" rather than "we don't know, so assume it's fine."

### Code-level issues

5. **`allocation_history.py` snapshots what was allocated, not why
   candidates were rejected — a smaller instance of the recurring
   pattern (items #3, #16.2, #18.3, #21.3).** It persists one full row
   per UTC day (idempotent upsert) with final weights/sleeves/equity —
   real, complete data for what happened, but nothing analogous for "why
   a candidate wasn't funded." Smaller gap than the other three instances
   since successful allocations are at least fully captured; the shared
   `RejectionRecord` shape from item #21.3 would extend cleanly here too
   if built.
6. **`research_link.py` has the same swallow-and-fail-open shape as item
   #17**, but with internally consistent timeouts this time (one shared
   `httpx.AsyncClient(timeout=10.0)` throughout `service.py`, no mismatch
   found) — in-process read first, HTTP fallback, then a fail-open
   default (empty list/`None`) with only a log line if both fail.

**Checked and confirmed clean**: `sizing.py`'s non-delegation to
`vinu_infra.risk_math.vol_target_scale` is a documented, reasoned choice
(unit mismatch between daily/annual vol conventions), not a repeat of the
duplication-mistake pattern — no Kelly/Sharpe reimplementation found
anywhere in `risk_budget.py`/`risk_utils.py`. `circuit_breakers.py` and
`risk_budget.py` both have solid, deliberate unit test coverage,
including regression tests for specific historical bugs (hysteresis-free
unrealized-PnL latching, abs-loss-vs-drawdown precedence). `game_plan.py`
is a pure dataclass module — the real logic lives in
`service.py:compute_daily_game_plan`, not a misleading name, just split
across two files.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Given findings #2 and #3 mean two risk controls could be
silently non-functional during a real drawdown, this is a strong
candidate for high priority.

**UPDATE (2026-09-26)**: finding #1's same-symbol netting gap now has a
defensive backstop at the `vinu-live` layer (`SignalTranslator.
_net_by_symbol`, item #24 finding #2's fix) — but that is downstream
damage control, not this finding's actual fix. `vinu-portfolio`'s own
`compute_daily_allocation`/`allocate_risk_parity` still allocate purely
per-strategy-name with zero symbol-level netting or conflict detection,
exactly as described above; the `SymbolConflict` shape and the open
net/keep-separate/block policy decision this finding calls for are both
still unbuilt -- deliberately not decided here either, same as it was
left for `vinu-live`, since it's the same real policy question, not a
default to assume just because a default was already picked once
downstream.

**UPDATE (2026-09-26, later same day)**: **findings #2, #3, and #4 are
now built and tested.** `compute_daily_allocation` (`service.py`) now
consumes both real risk signals this finding named as computed-but-
unread:
- **Finding #3** (the second risk-tiering system): `risk_budget.py`'s
  `compute_risk_budget` is now called in-process (same `self._risk_
  tracker` instance `compute_risk_status` already used, no cross-process
  issue here) and its per-symbol `suggested_size_multiplier` is folded in
  as one more bounded multiplicative tilt, same shape as regime/outcome/
  confidence-gradient -- exposed as `risk_budget_multiplier` per weight
  and `risk_budget` in the response.
- **Finding #2** (halve/flat unconsumed): real, cross-process fix, not a
  trivial in-process read -- `drawdown_scheduler.py`'s `monitor_main_loop`
  runs as its OWN OS process (same container, split by entrypoint.sh's
  `&`/`exec`, same shape as `vinu-live`'s scheduler/poller split), so
  `PortfolioService` can't just read `PortfolioDrawdownMonitor.action` in
  memory. New `storage/drawdown_status.py` (`DrawdownStatusStore`, same
  `SQLiteBackend` pattern `allocation_history.py` already uses) is the
  cross-process-visible signal: the monitor loop writes its real action
  every cycle, `compute_daily_allocation` reads it. **Deliberately NOT
  applied as a weight-tilt like finding #3** -- `target_weight` is always
  renormalized to sum to 1.0, so a *uniform* multiplier applied to every
  weight before that renormalization is a mathematical no-op. "Halve
  size"/"exit to flat" means less *total capital deployed*, so the action
  multiplier (ok=1.0/halve=0.5/flat=halt=0.0) applies to
  `deployable_equity` instead, the same place `reserve_fraction` already
  applies its own scale-down, and stacks with it rather than replacing it.
- **Finding #4** (silently inert on agent-API-down): built exactly as
  this finding's own concrete mechanism specified --
  `PortfolioDrawdownMonitor` gained `consecutive_unavailable_count`
  (`note_unavailable()`), reset on any successful `update()`, escalating
  to a real halt (via the same `_halt_trading` finding #2 already uses)
  once unreachability persists for `unavailable_halt_threshold` (3)
  consecutive cycles -- same "N consecutive cycles" shape
  `vinu-live`'s `RECON_DRIFT_ALERT_CYCLES` (item #24 finding #3's fix)
  already established, reused rather than reinvented.
- **A known, harmless redundancy this introduced, not hidden**:
  `compute_risk_status()` calls `compute_daily_game_plan()` ->
  `compute_daily_allocation()` internally, which now *also* fetches
  positions and computes `risk_budget` -- then `compute_risk_status`
  fetches positions and computes it AGAIN itself. Not a correctness bug
  (`DailyPositionTracker.record_unrealized_pnl`'s own "worst reading,
  immune to repeated identical reads" design, documented in its own
  docstring, makes the double-call idempotent), but a real duplicate
  fetch/compute this fix introduced, not yet folded into the
  `_returns_cache`/`_portfolio_cache` TTL-cache pattern this file already
  uses for exactly this class of problem elsewhere. Left as a named,
  scoped inefficiency, not silently ignored.
- **Finding #1 remains genuinely open** -- the real policy decision
  (net/keep-separate/block), same as stated in the UPDATE above.
- **43 new tests**, all passing: 13 in `test_circuit_breakers.py`
  (4 action-ladder + `TestConsecutiveUnavailableEscalation`'s 3, plus
  regression coverage), 4 in new `test_drawdown_status_store.py`, 3 in
  `test_drawdown_scheduler.py` (`TestRunOnceWritesTheStore`), and
  `TestComputeDailyAllocationDrawdownAndRiskBudgetTilts` (6) plus fixes
  to 5 pre-existing tests that needed a new `_fetch_positions` mock once
  this call path existed. Confirmed zero regressions: full `vinu-
  portfolio` suite, 230 passed (up from 209 before this round).

**UPDATE (2026-09-26, third pass same day)**: went back over this
item's own fix for loose ends before moving on, per instruction, and
found and closed two real ones:

- **The redundancy the previous update flagged and left open is now
  fixed.** `compute_risk_status()`'s call chain used to compute
  `risk_budget` twice per call (once inside `compute_daily_allocation`
  for its own tilt, once again from scratch in `compute_risk_status`
  itself). `compute_daily_game_plan` gained an optional `allocation`
  param (default `None` preserves every existing caller's behavior
  exactly); `compute_risk_status` now computes the allocation once and
  threads it through, reusing its already-computed `risk_budget` instead
  of re-fetching positions and recomputing. Verified with a spy on
  `compute_risk_budget` asserting exactly one call per
  `compute_risk_status()` invocation, not just asserted by inspection.
  4 pre-existing `TestComputeRiskStatus` tests had to be rewritten (they
  mocked `compute_daily_game_plan` wholesale, which no longer matches
  the real call shape) to mock `build_portfolio`/regime/equity instead
  and let the real call chain run -- a stricter, more realistic test than
  before, not a weaker one.
- **Finding #1's "not even a flag" half, closed.** New
  `_detect_symbol_conflicts` groups final weights by symbol and reports
  every symbol two or more strategies target, flagging opposite-direction
  cases loudly (same warning-log posture `SignalTranslator._net_by_symbol`
  already uses) -- exposed as `symbol_conflicts` in `compute_daily_
  allocation`'s response. Deliberately detection/visibility only, NOT a
  merge: this pipeline's entire tilt stack (confidence-gradient by
  deflated Sharpe, outcome-confidence by artifact_id, sleeve/interval
  bucketing) is keyed by STRATEGY identity throughout, so collapsing two
  strategies' rows into one here would silently orphan or corrupt all of
  that -- a much bigger, riskier surgery than this finding actually asks
  for ("netting/flagging," its own word for either). Real netting
  *enforcement* already happens correctly downstream, at the last point
  before an order is built (`vinu-live`'s `SignalTranslator.
  _net_by_symbol`, item #24 finding #2) -- what was genuinely missing
  was visibility at the conflict's actual source, which this closes. The
  net/keep-separate/block policy decision itself remains exactly as open
  as it was, same posture already documented for the vinu-live-layer fix
  -- a flag is not a policy.
- **6 new tests**, all passing: `TestDetectSymbolConflicts` (5) +
  1 spy test in `TestComputeRiskStatus`. Confirmed zero regressions: full
  `vinu-portfolio` suite, 236 passed (up from 230).

**UPDATE (2026-09-26, fourth pass same day)**: **finding #1's policy
question is now decided, not left open — net.** Re-examined it directly
rather than continuing to defer it:

- A single brokerage account cannot literally hold two opposing
  positions in the same symbol at once — "keep separate" isn't
  realizable without sub-accounts, which nothing in this system has or
  needs. "Block" would leave a stale/unmanaged position sitting whenever
  two strategies disagree, which is a worse outcome than converging on
  their actual net conviction. That leaves net as the only policy that's
  both realizable and doesn't introduce a new failure mode — and it's
  already exactly what `vinu-live`'s `SignalTranslator._net_by_symbol`
  (item #24 finding #2) has been doing correctly, at the one place it
  actually needs to happen (right before an order is built), this whole
  time. The decision isn't new code; it's naming what the system already
  does as the deliberate, closed answer instead of an unresolved
  question — `_detect_symbol_conflicts`'s own docstring and warning-log
  text (`vinu_portfolio/service.py`) now say so explicitly.
- Re-implementing netting a second time inside `vinu-portfolio` was
  considered and rejected on purpose, not just skipped: `compute_daily_
  allocation`'s entire tilt pipeline (deflated-Sharpe confidence-gradient,
  outcome-confidence by artifact_id, sleeve/interval bucketing) is keyed
  by STRATEGY identity throughout, so collapsing two strategies' rows
  into one this early would corrupt that bookkeeping — and a second
  enforcement point could only ever duplicate `vinu-live`'s math, never
  improve on it, while adding a real risk of the two computations
  silently drifting apart.
- What genuinely was still missing, closed now: `_detect_symbol_conflicts`
  gained `gross_weight` (sum of `|contribution|`) and `severity`
  (`1 - |net|/gross` — 0.0 when contributions barely overlap, up to 1.0
  when they fully cancel out), so a report or operator can tell "mostly
  agreement" apart from "strategies actively fighting" instead of just
  seeing a flat `opposite_direction: true/false`. New async
  `PortfolioService._notify_severe_symbol_conflicts`, called from
  `compute_daily_allocation` right after conflicts are computed,
  escalates the genuinely severe ones (opposite-direction, severity >=
  0.5, gross weight >= 0.05 — guessed starting constants, same posture as
  `FORWARD_HORIZON_BARS` elsewhere in this file, meant to be revisited
  once real data exists) to a real alert via a new `/notify/symbol-
  conflict` route on `vinu-agent`'s existing shared notify front door
  (same noise-gated, per-symbol-deduped, best-effort shape as
  `/notify/reconciliation-drift`, item #24 finding #3 — reused, not
  reinvented). WARNING severity, not CRITICAL: netting already handles
  the conflict correctly, so this is informational escalation for a
  human, not an unmanaged-money-risk alert. Best-effort and never raises
  back into the allocation computation, same posture `_halt_trading` and
  every other `/notify/*` caller already establish.
- 13 new tests: 7 in `vinu-portfolio`'s `test_service.py`
  (`TestNotifySevereSymbolConflicts` — escalates when severe, never
  escalates a same-direction conflict regardless of size, never
  escalates a low-severity or too-small-to-matter conflict, a failed
  notification doesn't raise, multiple severe conflicts each get their
  own call — plus a `severity`/`gross_weight` assertion added to each
  existing `TestDetectSymbolConflicts` test and a new fully-offsetting-
  is-severity-1.0 case) and 3 in `vinu-agent`'s `test_routes_notify.py`
  (delivers and describes the disagreement, no-channels-configured, and
  per-symbol dedup — same shape as the existing reconciliation-drift
  tests). Confirmed zero regressions: full `vinu-portfolio` suite, 243
  passed (up from 236, exactly +7); full `vinu-agent` `test_routes_
  notify.py`, 15 passed (up from 12, exactly +3).

**UPDATE (2026-09-26, fifth pass same day)**: **finding #5 fixed** —
`allocation_history.py` now also records why a candidate wasn't funded,
using the same `RejectionRecord` shape item #18 finding #3 already
wired into the screener's own instance of this pattern.

- Checked what "rejected" even means in this pipeline before writing
  anything: unlike `vinu-screener`'s hard filter, nothing in
  `allocate_risk_parity`/`compute_daily_allocation` makes a binary
  accept/reject call — every strategy gets SOME weight, possibly one
  that rounds to zero after four independently-computed multiplicative
  tilts (regime alignment, outcome confidence, confidence-gradient,
  risk-budget) and renormalization. So "not funded" here means
  `target_weight` rounding to ~0, and "why" is necessarily a heuristic
  over the tilt values the response already exposes (`regime_multiplier`
  /`outcome_multiplier`/`confidence_gradient_multiplier`/`risk_budget_
  multiplier`, all already computed per weight entry — no new
  computation needed, just reading what's already there) — the smallest
  multiplier if any is below 1.0, or `"concentration_or_dilution"` if
  every tilt was neutral and the zero came from `cap_concentration`'s
  redistribution or plain dilution across many strategies instead.
  Documented as a heuristic in the code, not oversold as a definitive
  single cause the way a hard-filter bound violation is.
- New `PortfolioService._detect_not_funded()` (pure, static — same shape
  as `_detect_symbol_conflicts`), called from `compute_daily_allocation()`
  right after the tilt stack finishes. Exposed as `not_funded` in the
  real HTTP response (`compute_daily_allocation`'s response dict passes
  straight through to the route, no extra wiring needed there) and
  persisted on `allocation_history.py`'s own daily row (`not_funded`
  column, migration, `SCHEMA_VERSION` 1 -> 2, same fail-open-to-`[]`
  handling for a pre-migration row every other migrated column in this
  audit series already uses).
- 8 new tests: 2 in `test_allocation_history_storage.py`'s new
  `TestNotFunded` (round-trip, pre-migration fail-open) and 6 in
  `test_service.py`'s new `TestDetectNotFunded`
  (a funded strategy isn't reported, the smallest-multiplier
  categorization, the all-neutral-tilts `concentration_or_dilution`
  case, a tiny-but-nonzero weight is still caught, multiple unfunded
  candidates each get their own record, and the real end-to-end wiring
  test confirming `not_funded` reaches both the HTTP response AND the
  persisted history row through one real `compute_daily_allocation()`
  call). Confirmed zero regressions: full `vinu-portfolio` suite, 251
  passed (up from 243, exactly +8).

## 24. vinu-live audit (2026-09-25) — Layer 6, the highest-priority item in this file: two critical gaps in the real-money execution path

Real, verified findings in the only layer that touches actual money.
Given the stakes, extra scrutiny was applied, and two findings confirm
and sharpen item #23's gaps rather than being unrelated new ones.

### Process/design issues

1. **CRITICAL — the main rebalance path never checks risk-limit
   breakers at all, confirming and localizing item #23's finding.**
   `vinu_live/scheduler.py`'s `LiveScheduler.cycle()` (60-121, the path
   that actually executes portfolio-level rebalances from `vinu-portfolio`)
   calls straight through `_translator.translate()` → `_plan_execution()`
   → `_execute_plan()` with **no call anywhere** to the real risk-limit
   checks (daily loss, VaR, leverage, cluster exposure, position count)
   that live in `breaker/engine.py`'s `check_limits()`. Those checks only
   run inside a *separate*, signal-driven path
   (`trade_plan/orchestrator.py:2001`'s `_check_breaker`). If that other
   worker isn't running, or hasn't yet tripped its own breaker, this main
   path will blindly execute whatever weights `vinu-portfolio` hands
   it — now we know exactly why item #23's `halve`/`flat` actions have no
   consumer: the layer that should be checking them isn't wired to check
   *any* risk limits on this path, not just those two specific actions.
   Fix: call `check_limits()` (or reuse `_check_breaker`) inside
   `LiveScheduler.cycle()` before `_plan_execution`, gated on the same
   `BreakerState`/halt mechanism the orchestrator already uses correctly.
2. **CRITICAL — the same-symbol conflict from item #23 is unhandled here
   too, and now the concrete failure mode is known.**
   `SignalTranslator.translate()` (`signal_translator.py:43-93`) iterates
   `target_weights` as a flat list and builds one `OrderInstruction` per
   entry, keyed only by `symbol` for close-out logic — it never dedupes
   or nets entries sharing a symbol. If `vinu-portfolio` emits two entries
   for the same symbol from different strategies (item #23's exact gap),
   this produces **two independent orders**, each computed against the
   *same unchanged* position snapshot, not against each other. Concrete
   example given: Strategy A wants +0.05, Strategy B wants -0.03 on the
   same symbol → both a buy and a sell instruction get generated and
   submitted in the same cycle — a real buy-then-sell whipsaw instead of
   a netted +0.02 target. This is genuinely unhandled, not an intentional
   design choice. Fix: aggregate `target_weights` by symbol (per whichever
   policy gets chosen for item #23's open netting-policy decision) before
   `translate()` runs — ideally at the `vinu-portfolio` boundary, but
   defensively also inside `SignalTranslator` itself as a second layer of
   protection.
3. **Reconciliation drift is detected but never alerted on this path.**
   `scheduler.py`'s cycle builds a `ReconciliationReport` with
   `drift_detected`/`n_drifts`/`total_drift_pct`, but `cli.py::worker_main`
   only logs the overall status — never inspects the reconciliation
   result. A *different* code path
   (`trade_plan/orchestrator.py:2797-2820`) does this correctly: on drift,
   it auto-corrects the book AND calls a real notification function. So a
   broker/expected-position mismatch on the main rebalance path is
   silently absorbed into a dict nobody reads. Fix: wire
   `LiveScheduler`'s recon report through the same notify path the
   orchestrator already uses correctly.

### Checked carefully and confirmed genuinely good, given the stakes

4. **Kill switch is correctly placed and checked from both paths.**
   `trade_plan/guards.py::halt_reason()` checks both a local halt file and
   the agent's cross-process halt flag, called right before the literal
   broker POST in `scheduler._execute_plan` (and again mid-plan between
   slices) and by the orchestrator. Fail-closed on local failure,
   fail-open only on remote-fetch network failure. Correctly placed —
   closest to the broker, nothing upstream can bypass it.
5. **Money/quantity handling correctly uses `Decimal`, not float,
   throughout** — `book/quantize.py` converts via `Decimal(str(x))`
   (never `Decimal(float)`, which would reintroduce the exact
   floating-point error it's trying to avoid), and all sizing math stays
   in `Decimal` until the final `OrderInstruction` boundary. No
   floating-point precision bug found in this classic risk area for money
   handling. Minor caveat, not independently verified: the SQLite ledger
   itself stores `REAL` (float) columns per the module's own docstring,
   claimed exact for cent-quantized values.
6. **A real idempotency key exists** — `client_order_id`, built from
   symbol/side/qty/slice/minute-bucket, sent with every broker order.
   Flagged as **needs verification**: whether the broker/agent-api
   actually enforces uniqueness on this key lives outside this directory
   and wasn't independently confirmed.
7. **Needs verification, not confirmed either way**: the approval
   worker's fail-closed posture on a 409 (not-yet-approved) looks correct
   by inspection, but there's no test confirming the orchestrator truly
   never acts on a still-unapproved plan — flagged honestly as unverified
   rather than assumed safe.

### Code-level

8. **Thin test coverage exactly where finding #2 lives**:
   `tests/test_signal_translator.py` (91 lines) has no test for two
   `target_weights` entries sharing a symbol — confirming finding #2 was
   never exercised by any test. `reconciliation.py` has minimal direct
   tests; nothing asserts `LiveScheduler.cycle()` actually surfaces or
   alerts on detected drift.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Given this is the only layer touching real money, and two
findings are rated CRITICAL with concrete, demonstrated failure modes
(blind execution past risk limits; a real buy-then-sell whipsaw), this is
the single highest-priority item in this entire file.

**UPDATE (2026-09-26)**: **findings #1 and #2, the two CRITICAL gaps,
are now built and tested** — see `reverse-engineering/
06-execution-handoff-and-architecture.md` (design) and `reverse-engineering/
02-implementation-status.md`'s 2026-09-26 entries (build log). Concretely:
`LiveScheduler.cycle()` (`scheduler.py`) now calls `check_limits()` via a
new `_check_breaker()` before `_plan_execution`, modeled directly on
`orchestrator.py`'s own working `_check_breaker`/`_engage_real_halt`
pattern (finding #1) — deliberately scoped, still passes
`covariance_matrix=None` since `_compute_covariance` remains
orchestrator-specific, so the aggregate-VaR check is skipped while every
other check (daily loss, position count, cluster exposure, leverage)
runs in full. `SignalTranslator.translate()` now nets `target_weights` by
symbol before building instructions (`_net_by_symbol`, finding #2) —
"net" chosen as the provisional default per finding #2's own framing that
this is a real policy call, not a safe assumption; item #23 finding #1's
own netting gap at the `vinu-portfolio` layer is still open, so this is a
defensive backstop at the last layer before an order is built, not the
fix at the source. Point 7 of the reverse-engineering series also went
one step further than this item asked for: a live-decision EXECUTE
verdict (a new capability built alongside this fix, not originally part
of item #24) now flows through this same hardened path via
`LiveScheduler._fetch_live_decision_weights()`, so it inherits both
fixes automatically.

**UPDATE (2026-09-26, later same day)**: **finding #3 is now also
fixed** — all three findings in this item are closed. `LiveScheduler`
gained `_handle_reconciliation_drift`, wired to the same
`/notify/reconciliation-drift` front door `orchestrator.py`'s book-vs-
broker check already uses (extended with a new `action=
"target_weight_drift"`, since this is a genuinely different comparison —
target weight vs. broker position, not internal book vs. broker).
Deliberately not "alert on any drift in the report": this recon compares
a target that just changed *this* cycle against positions fetched
*before* this cycle's own orders were submitted, so routine per-cycle
drift is an expected gap those orders are already closing, not an
anomaly — instead it only alerts once a symbol's drift persists for
`RECON_DRIFT_ALERT_CYCLES` (3) consecutive cycles, edge-triggered, same
"N consecutive cycles" shape item #23 finding #4 already recommends for
its own `consecutive_unavailable_count`. See `reverse-engineering/
02-implementation-status.md`'s 2026-09-26 entries for the full build log.

## 25. Cross-check against prior recorded expectations (2026-09-25) — the maturity-agentic-system and high-expectations folders

The user asked five direct system-designer questions and pointed at two
prior planning folders
(`missing-pieces-of-system/maturity-agentic-system/`,
`high-expectations/chatgpt-version/`) to check whether the current
system, plus everything jotted in this file, actually meets what was
already recorded as expectations elsewhere. Answered by reading both
folders in full and verifying every claim against real code — not
trusting either the prior docs or this file's own claims without
re-checking.

1. **Live data filling (items #15/#19) has no plan anywhere, in this
   file or the maturity-agentic-system folder.** Grepped the entire
   maturity-agentic-system folder for anything touching data freshness/
   point-in-time correctness — nothing. That folder is about system
   self-*confidence*, a genuinely different concern from data-freshness
   correctness. Items #15/#19 remain fully open, unaddressed by anything
   already designed elsewhere.
2. **Two independent evidence pipelines exist, with very different real
   status — worth being precise about which is which.** Track 1's
   must-condition evidence still doesn't reach `HypothesisRegistry` or
   anywhere downstream (item #1, confirmed still true). But a **real,
   already-built** pipeline exists alongside it: `MaturityAssessor`'s
   tier (a system-confidence signal — `cold_start`/`paper_only`/
   `early_live`/`mature`, based on real trade counts/calibration
   accuracy/regime coverage, see
   `maturity-agentic-system/00-maturity-agentic-system-explanation.md`)
   is verified, in real code, to reach LLM prompts today:
   `vinu_research/trade_plan_authoring.py:888-907` builds a
   `maturity_context`, and `forecast_skill.py:253-263` renders a real
   `"=== System Maturity ==="` block into the prompt when the (opt-in,
   default-off) `maturity_tier_enabled` flag is set. This is the one
   evidence pipeline found across this entire audit series that is
   confirmed to work end-to-end already, even if off by default.
3. **The system cannot safely handle itself autonomously yet, and
   maturity-awareness was never meant to fix this — confirmed as two
   genuinely separate axes, not overlapping ones.** Items #23/#24's gaps
   (circuit breaker actions unconsumed, no risk-limit check in the main
   live rebalance loop, unhandled same-symbol conflicts) are completely
   real and completely unaddressed by the maturity design, which only
   ever answers "how confident should the system be given its evidence,"
   consumed by `risk_gatekeeper`/`capital_allocator` as *one more input*
   to decisions those components already make — not a mechanism that
   makes those decisions happen in the first place. Even a fully built,
   fully wired `MaturityAssessor` would not fix the fact that
   `LiveScheduler`'s main cycle never calls `risk_gatekeeper`'s limit
   checks at all (item #24 finding #1). Both fixes are needed; neither
   substitutes for the other, and no document anywhere conflates them.
4. **A real, well-justified, already-scoped agent opportunity — stronger
   than any candidate found earlier in this session.** Reconciliation-
   drift interpretation and same-symbol netting (candidates considered)
   are both plumbing/deterministic-policy fixes, not agent work. The
   genuine find: `maturity-agentic-system/thinking-1/02-decided-pattern/
   00-decided-pattern.md` (§8) already designs a "step-8 synthesis agent"
   meant to read across 24 real, live reflection analysts' findings
   (written to a real, tested, populated `reflection_beliefs` table) and
   notice when separate findings are actually one story — e.g. a
   regime-wide risk-off move connecting a degradation finding on one
   ticker with a correlation spike on others (the doc's own worked
   example). This is **explicitly scoped out of the current
   implementation** (`07-implementation-plan-status.md:99-103,721-729`),
   despite the data it would reason over already existing and sitting
   completely unconsumed (`07-implementation-plan-status.md:761-765`
   calls this out directly as still open). This is the strongest agent
   candidate found across this whole audit series, precisely because the
   material already exists — unlike a hypothetical agent proposed against
   data that doesn't exist yet.
5. **No overlap between the maturity-agentic-system's tables and any of
   the tables proposed across items #1-24 — checked by name and by shape
   in both directions, build both sets as designed.**
   `01-table-schemas.md`'s 3 real tables
   (`reflection_findings_history`, `reflection_beliefs`,
   `reflection_synthesis_outcomes`) are purpose-built for "how
   self-aware is the system" — a different question than this file's
   proposed `live_snapshots`, `cross_track_check`, `MoveEvidenceStore`,
   and `RejectionRecord`, which all answer "what evidence backs this
   specific move/candidate/rejection." Grepped both directions: zero
   name collisions, zero conceptual overlap. These are genuinely separate
   gaps needing genuinely separate tables — the "check before you build"
   principle applied here found no duplication to avoid, which is itself
   a useful, checked answer rather than an assumption.

**Nothing in this item has been acted on** — recorded per instruction, no
code changed. Point 4 (the step-8 synthesis agent) is a strong candidate
for the "any other place a dedicated agent helps" question raised
earlier in this file, given real, unconsumed data already exists for it
to reason over today.

**UPDATE (2026-09-27)**: **a fresh re-read of `high-expectations/chatgpt-version/`'s
two source docs, checklist-style against the real current code (not this
item's own earlier 5-question pass) — most of the senior-quant
expectation list turned out to already be built.** Confirmed directly,
not assumed: bull/bear/risk multi-agent debate (`vinu-agent`'s
`investment_committee` swarm preset — real, but opportunistic/async, not
a mandatory gate on every trade, kept that way on explicit instruction,
not a gap), a self-calibrating Trade Score (`trade_score_calibration.py`,
literally built as a "high-expectations follow-up" per its own
docstring, predating this pass), a real kill switch
(`circuit_breakers.py`'s `_halt_trading`, wired into the main cycle per
item #24), VWAP/TWAP execution slicing (`vinu-live/execution.py`),
market-memory historical-analogue matching (`trend_lifecycle/patterns.py`'s
KNN library), and the `live_decision` continuous re-evaluation/thesis-
invalidation loop (reverse-engineered and built earlier in this same
file's thread). A handful of genuine gaps were found and closed on
explicit instruction to build them:

- **Composite position sizing** — see item #14's own dated update above
  for the full `CompositeSizer` build (vol-target + correlation-aware,
  via the relocated `vinu_tools/compute/risk/shock_correlation.py`).
- **A unified "why isn't this trading" view** — turned out to already
  exist (`vinu_infra/strategy_evaluation.py`'s `StrategyEvaluationStore`,
  already consolidating every gate's verdict into one current-state
  summary) but had no HTTP surface anywhere. New
  `GET /research/evaluation-status/{artifact_id}`,
  `GET /research/evaluation-status/by-ticker/{ticker}`, and
  `GET /research/evaluation-history/{artifact_id}` — read-only, no new
  gate or abstraction invented. 9 new tests (`vinu-research` +
  `vinu-infra`).
- **A hard risk:reward floor** — checked and found already built and
  already enforced (`gates/trade_score_gate.py`'s `_reward_risk_ratio()`
  force-sets `no_trade` below `min_reward_risk_ratio`, called live in
  `trade_plan_authoring.py`'s gate chain) — corrected from an earlier,
  wrong "partial" claim rather than silently building a redundant second
  check.
- **Gradual capital scaling** — a system-wide `MaturityAssessment`
  (cold_start/paper_only/early_live/mature, already wired into an LLM
  prompt) never touched capital sizing. New, opt-in (default off)
  `maturity_capital_gating_enabled` in `vinu-portfolio`, scaling
  `deployable_equity` by a configurable per-tier multiplier — the same
  whole-portfolio mechanism the drawdown ladder already uses, since
  maturity is one system-wide value, not a per-strategy signal. Fails
  open to full capital on any error. 8 new tests.
- **Search-trends alternative data** — the one named alt-data source
  with no paid-tier or missing-consumer blocker (order-book depth and
  on-chain data were checked alongside it and explicitly deferred: L2
  needs a paid Alpaca/Polygon tier this pass can't provision, and
  on-chain has zero real consumer since this system only trades
  equities today). New `search_trends` angle (`vinu-initial-analysis`,
  30th angle), via `pytrends` (no API key needed), weekly Google search
  interest with a rolling z-score, plus a real forward-return
  correlation backtest — fails open to a `no_data` row on any fetch
  failure, same posture every other external-data angle already uses.
  13 new tests.
- Confirmed zero regressions across every touched service:
  `vinu-simulator` 262 passed, `vinu-tools` 175 passed, `vinu-portfolio`
  259 passed, `vinu-research` 1123 passed/1 skipped, `vinu-infra` 314
  passed. `vinu-initial-analysis`'s full suite still can't run end-to-end
  in this environment (pre-existing torch-dependency collection errors,
  confirmed via `git stash` to predate this change) — a targeted sweep
  of every non-ML-dependent test file plus the new angle's own 13 tests
  passed (73 total), the same honest scope this file has used for this
  component before.
- **What this leaves open**: order-book/on-chain alt-data (deferred, not
  built), mandatory (blocking) investment-committee gating (declined,
  kept async on explicit instruction), evidence-confidence and
  drawdown-aware sizing factors (item #14's own remaining scope).

**UPDATE (2026-09-27)**: **checked whether the high-expectations work, the
`live_decision` reverse-engineering work, and the maturity-agentic-system
vision are mutually compatible (yes — confirmed no conflicting design
anywhere, each answers a different question), then built the two
maturity-tier consultation points (#2/#3) the reverse-engineering doc's
own step-3 phasing had marked "still not started."** Point #1 (no exit
mechanism exists for a `live_decision`-opened position — reconciliation
only ever reports drift on it, never acts) was investigated and confirmed
real via direct code reading (`vinu-live/vinu_live/book/schema.py`'s
`Position.artifact_id` docstring: "empty for positions opened outside the
Phase 6 trade-plan orchestrator"; `TradePlanOrchestrator`'s HOLD/ADD/
REDUCE/EXIT engine is keyed only on artifact_id; no per-position close
HTTP route exists anywhere in `vinu-live/vinu_live/server/app.py`) but
deliberately **not built this pass** — flagged for confirmation first
given live-money stakes, per instruction. Points #2 and #3, built:

- **Point #2 — risk_gatekeeper consults the maturity tier.** New
  `GET /research/maturity/status` (`vinu-research`, always-on, read-only,
  not gated by `maturity_tier_enabled` since that flag only ever
  controlled trade-plan authoring's own LLM prompt). New shared
  `vinu-infra/maturity_consultation.py`'s `MaturityConsultationStore` — one
  queryable log across every consumer/service of "who consulted the tier
  and what they did about it," same "one queryable place" reasoning
  `StrategyEvaluationStore` already established. New
  `vinu-live/vinu_live/maturity_link.py`: `fetch_maturity_status()`
  (fails open to `None` on any fetch error) and `scale_limits_for_tier()`
  (a pure function scaling every `BreakerLimits` numeric field by a
  per-tier constant — 0.25/0.5/0.75/1.0 for cold_start/paper_only/
  early_live/mature, floored so trading never becomes structurally
  impossible even at the strictest tier). Wired into
  `LiveScheduler._check_breaker()` via a new `_maturity_scaled_limits()`
  method, gated by `risk_gatekeeper_maturity_scaling_enabled` (opt-in,
  off by default). 15 new tests (`vinu-live`); full suite still 526
  passed (the same 3 pre-existing, unrelated `ModuleNotFoundError:
  vinu_agent` collection errors persist, confirmed environmental).
- **Point #3 — live_decision consults the maturity tier, in the right
  place.** Verified via the reverse-engineering doc's own point 8 that
  the real deciding agent lives in `vinu-agent`, not `vinu-live` (this
  service only has the poller/detector/tracker) — so the knob and the
  wiring both moved there instead of staying in `vinu-live`. Removed the
  now-confirmed-dead `live_decision_maturity_scaling_enabled` field this
  session had first (wrongly) added to `vinu-live/vinu_live/config.py`
  rather than leaving unused config behind. New
  `AgentConfig.live_decision_maturity_scaling_enabled` (opt-in, off by
  default) in `vinu-agent/vinu_agent/config.py`. Wired into
  `vinu-agent/vinu_agent/tools/get_live_decision_context_tool.py` — the
  real, natural composition point for everything `live_decision_agent`
  reads before deciding EXECUTE/SKIP — adding a `maturity_status` field
  (empty when disabled or on fetch failure) alongside every consultation
  logged to the same shared `MaturityConsultationStore`. Never a hard
  gate: read-only context for the LLM's own final answer, same posture
  as every other field this tool already returns. 5 new tests
  (`vinu-agent`: 3 for the tool, 2 for the config knob — the tool's own
  4 pre-existing tests stayed green unchanged, 7 total in that file
  now). Full suite: 1437 passed, 4 skipped (the 16 failures/2 errors
  seen in a full run are pre-existing, environmental — `openai` and
  `vinu_live` not installed in this venv, confirmed via direct
  traceback, not caused by anything touched this pass).
- **What this leaves open**: point #1's actual fix (still awaiting
  confirmation), the combined "narrating agent" + "step-8 synthesis
  agent" (confirmed to be **one and the same agent** per
  `00-decided-pattern.md` §8's own words — "one seat, not two" — not yet
  started), and item #14's remaining evidence-confidence/drawdown-aware
  sizing factors.

**UPDATE (2026-09-27)**: **built step 8, "the brain" — the combined
narrating-agent/synthesis-agent points #4/#5 — on explicit instruction,
with the scope honestly narrower than the design doc's own full vision,
documented as such rather than silently smaller.**
`25-A-Y-details/07-implementation-plan-status.md`'s own "where to
continue, ranked" list had flagged this exact item: "Deliberately not
started without its own design pass first — building it as specced right
now would mean inventing that design on the fly." That design pass
happened now, on explicit instruction, and is recorded here rather than
hidden:

- **Hindsight is not wired, and cannot be yet** — grepped the entire
  codebase for a real Hindsight client before writing anything: zero
  exist, only docstring mentions of a "future" integration, despite a
  `hindsight-llm` container actually running in this stack. v1 reads
  Layer 0 (`reflection_beliefs`) only — the design's own "hard, always-
  trustworthy" fallback store, not a workaround.
- **The "6-axis maturity profile" the design doc left undesigned**: this
  build defines the 6 axes as the 6 analyst clusters step 3 already
  settled (Forecast Intelligence, Regime & Risk Coverage, Execution &
  Money-Flow, Decision-Process/Cognition, Governance & Freshness,
  External-Signal Cross-Check), each scored `healthy`/`degrading`/
  `insufficient_evidence` by one LLM call, grounded only in real belief
  rows — never an invented scalar.
- **`reflection_synthesis_outcomes`** — the real, persisted intermediate
  table, built to `01-table-schemas.md`'s own 12-column spec exactly
  (not simplified), in `vinu-infra/reflection.py`:
  `record_synthesis()`/`get_latest_synthesis()`/`list_pending_syntheses()`/
  `resolve_synthesis()`. 6 new tests.
- **`vinu-reflection/vinu_reflection/reflection/brain.py`** (new) — the
  synthesis logic: `gather_synthesis_inputs()` (pure — every currently
  notable/significant belief, across all clusters; empty most cycles,
  same "routine, nothing written" outcome every one of the 24 analysts
  already produces most of the time, which is what keeps the one real
  LLM call bounded rather than firing every cycle regardless), one LLM
  call via `run_synthesis()` (reuses `vinu_agent.agent.llm`'s
  `ChatLLM`/`create_llm_from_config` in-process — `vinu-reflection`
  already depends on `vinu-agent` directly for 12 other analysts, so
  this is the same "mount-and-import" posture, not a new dependency),
  fails open to "wrote nothing this cycle" on any LLM failure or
  malformed response (never a half-written row). Self-trust tracking via
  `resolve_pending_syntheses()` is real and **mechanical, not LLM-graded**
  — a second LLM call judging the first would only compound uncertainty
  on top of uncertainty; only `threshold_nudge` predictions carry a
  claim checkable against `reflection_beliefs`' own subsequent state
  (did the targeted belief get freshly re-confirmed as still
  `significant`, or not), every other action type resolves
  `inconclusive`, honestly, rather than guessed. New opt-in
  `ReflectionConfig.brain_synthesis_enabled` (off by default) plus its
  own decoupled `brain_synthesis_worker_interval_sec` (hourly, separate
  from the analysts' own 5-minute cycle — re-synthesizing an unchanged
  picture every 5 minutes would waste real LLM calls), wired into
  `cli.py`'s existing worker loop. 14 new tests for `brain.py`, 4 for
  the new config fields.
- **Never places an order or touches the kill switch** — `proposed_action`
  is read-only output, exactly matching the design's own constraint on
  what the brain may ever do.
- **Step 9 (a real consumer acting on the brain's output) is
  deliberately NOT built this pass, and not a corner cut** — checked
  first: every one of the design's own named consumers
  (Planner/vinu-agent, risk_gatekeeper/vinu-live,
  capital_allocator/vinu-portfolio) is **already a declared dependency
  of `vinu-reflection`** (it mounts and imports all three in-process for
  its existing 24 analysts). Any of them importing `vinu-reflection`
  back would be a real circular package dependency, not just an
  inconvenience — so an HTTP surface is structurally required here,
  never optional, and `vinu-reflection` has no FastAPI server today by
  deliberate original design (`config.py`'s own docstring: "this
  service, today, is a worker loop only"). Standing one up is real,
  separate, correctly-scoped work for later, not folded into this pass.
- Confirmed zero regressions: `vinu-infra` 327 passed. `vinu-reflection`
  itself cannot run its full suite in this environment at all —
  confirmed via direct traceback that `vinu_agent`/`vinu_live`/
  `vinu_screener` are not installed in this shared Python environment
  (the same class of pre-existing, environment-wide gap as `vinu-agent`'s
  own missing `openai` and `vinu-live`'s missing `vinu_agent`/`vinu_live`
  cross-installs found earlier this pass) — confirmed pre-existing, not
  caused here, by checking that untouched sibling files
  (`regime_drift.py`, `angle_trust.py`) fail on the exact same import.
  This session's own new/touched files (`test_brain.py`, `test_config.py`)
  run cleanly in isolation: 18 passed.

## 26. Honest answer: are the components properly connected for the planned goals? No — here is exactly where the seams are broken

Asked directly: "can I say every component is properly internally
connected for the goals we've planned?" The honest answer, given
everything found across items #1-25, is **no** — this whole audit series
exists precisely because the seams keep turning out broken, not because
the individual components are badly built. Recorded here as one
consolidated, undiluted answer so it isn't left as something only said in
chat and then lost.

**Evidence doesn't flow where it should:**
- Track 1's must-condition evidence never reaches `HypothesisRegistry`
  (item #1).
- The research loop's own generation-time candidates get discarded before
  backtest, never recorded anywhere (item #16.2).
- `vinu-reflection`'s continuous findings sit in their own store,
  unconsumed by anything — the step-8 synthesis agent that would connect
  this is explicitly designed but not built (item #25.4).
- Three separate evidence-producing mechanisms, none feeding the one
  registry already built to consume exactly this (item #21's "three
  disconnected evidence streams" pattern).

**Risk signals get computed but never enforced downstream:**
- ~~`vinu-portfolio`'s circuit breaker computes `halve`/`flat` actions —
  nothing consumes them~~ — **fixed 2026-09-26**, see item #23's UPDATE:
  `compute_daily_allocation` now reads the real action via a new
  cross-process `DrawdownStatusStore` and scales `deployable_equity`
  accordingly.
- ~~A second risk-tiering system is exposed via an API nobody reads~~ —
  **fixed 2026-09-26**: `risk_budget`'s per-symbol `suggested_size_
  multiplier` is now a real multiplicative tilt in `compute_daily_
  allocation`, not just a `GET /risk/status` response nothing else reads.
- ~~`vinu-live`'s main execution loop doesn't call risk-limit checks at
  all~~ — **fixed 2026-09-26**, see item #24's UPDATE: `LiveScheduler.
  cycle()` now calls `check_limits()` before planning/executing any
  order. This was the single most serious gap in this whole synthesis
  item (real money, no risk check at all) — it no longer describes the
  system's current state.
- Same-symbol conflicts between strategies: **partially fixed**.
  `vinu-live`'s end now nets (item #24 finding #2, fixed 2026-09-26,
  `SignalTranslator._net_by_symbol`) — but `vinu-portfolio`'s own
  allocation step (item #23 finding #1) still does zero netting or
  conflict detection at the source. The gap moved from "unhandled
  anywhere in the chain" to "unhandled at the point of origin, caught
  defensively one layer downstream" — real progress, not the full fix
  this bullet originally described.

**The same computation isn't actually guaranteed to be the same
computation:**
- Indicator math (ADX, ATR, RSI-family) is independently reimplemented in
  at least 4 places (`vinu-screener`, `vinu-stock-price`,
  `trend_lifecycle`, and the original Track 1 mistake) — two of those
  (ADX, ATR) confirmed to have real formula bugs (item #20).

**Point-in-time safety is enforced by convention, not by the system:**
- Neither `vinu-stock-price` nor `vinu-news` enforces as-of correctness
  server-side — it only works today because callers happen to remember
  to clamp it, and `vinu-news` has a silent timestamp-conflation bug on
  top of that (item #19).

**The pipeline's entry point isn't actually live either:**
- Ticker discovery comes from a static seed list, with `vinu-screener`
  only an optional contributor, not the live source of truth the overall
  design assumes (item #16.5).

**The honest overall status**: this is a collection of well-built
individual components with real, working logic inside each one — but the
*connections between them*, which is where "the plan" actually lives, are
the part that's mostly still missing, inconsistent, or silently
unenforced. This is not a discouraging finding, it is the finding —
exactly why auditing layer by layer before building anything new on top
of this was worth doing.

**Nothing in this item has been acted on** — it is a synthesis of items
#1-25, not a new discovery, recorded here explicitly per instruction so
it is not left only said in conversation.

**UPDATE (2026-09-26)**: this overall "no" verdict still stands — most of
the seams named above (evidence fragmentation, duplicated indicator math,
point-in-time enforcement, the static ticker-discovery seed, three of
item #23's four findings) are completely untouched. But it is no longer
accurate to say *nothing* has been acted on: the single most serious
individual seam named in this item — `vinu-live`'s main execution loop
never checking risk limits at all — is fixed, along with a real, tested,
new connection this audit series didn't originally ask for: a live
must-condition firing can now flow all the way from a candle close
through a stage/state tracker, an LLM agent that reads real historical
evidence before deciding, and (if it decides EXECUTE and the strategy is
sized) into a real order through this now-hardened path. See
`reverse-engineering/00-overview.md` for what that connection is and
`02-implementation-status.md` for what's built vs. still open across all
9 of its own points. This folder's overall status line (`00-overview.md`)
has been updated to reflect this — it is no longer accurate to say
nothing in this folder has been implemented.

## Why these are jotted down together, not solved together

These five are genuinely different in scope and dependency order — #1
and #2 can be discussed now, #4 depends on Phase 3/Track 2 aggregate mode
existing first, #3 raises a real trust/tagging question before any code
gets written, and #5 is closest to the already-known "live detector"
gap. Recording them here means none of them get lost or have to be
re-explained later, without forcing a decision on any of them before
they've each been thought through on their own.
