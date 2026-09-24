# Planning: settled decisions, added one at a time

This file tracks concrete decisions for the design in
`00-explanation.md`, added incrementally as each piece gets settled in
discussion rather than written all at once. Treat entries as append-only
and dated — if a later decision changes an earlier one, add a new entry
that says so rather than silently editing the old one away.

**Foundational / cross-cutting — read first**: Decision 4 (model
on/off + per-angle model-selection policy, living in `vinu-infra`)
governs how every model-based supporting indicator in this plan (chronos
and the other foundation-model angles) actually gets computed. Kept in
sequence below to preserve the append-only log, flagged here so it isn't
missed on a top-down read.

## Decision 1 (2026-09-24): recording is dumb and total; analysis is separate and re-runnable

**The rule**: at recording time, do not pre-bucket, pre-threshold, or
pre-decide anything. Just record everything, raw.

Concretely, when a must-condition fires:
- Snapshot the **raw value** of every supporting indicator available at
  that moment (the full list from Decision-pending "all possible
  supporting indicators," including the existing 28-angle outputs from
  `vinu-initial-analysis` — no new computation needed there, they already
  run per symbol on their own cycle) — not a bucketed/binned version of
  each value.
- Record the **full outcome path** for the standardized horizon, not
  just a single collapsed return number: max favorable excursion, max
  adverse excursion, and return-at-horizon. A single final-return number
  would lock in one R-target's answer at record time; the raw path lets
  any R-target (1R, 2R, 3R, ...) be evaluated later, retroactively,
  without re-recording anything.
- No bucket edges, no quantile thresholds, no cluster weighting, no
  minimum-sample gating applied at this stage. Those all happen in the
  analysis layer, on top of the stored raw rows.

**Why**: every one of the buckets/thresholds/edges discussed
(quantile bins, cluster-robust weighting, sample-size gating, which
R-target to score against) is itself a design choice that can be wrong,
improved, or need re-validation over time (e.g. via the existing
`sweep_grid.py` walk-forward/PBO machinery). If those choices are baked
in at recording time, fixing or re-testing them later means the
historical data is unusable for the new approach. Keeping the raw
storage layer dumb and complete means every analysis decision downstream
can be re-run, re-validated, or replaced at any time against the exact
same historical record, with nothing lost.

**What this implies for the schema** (one row per trigger event):
`trigger_id, symbol, trigger_time, must_condition(s) that fired, {one
raw column per supporting indicator, including all 28 angle outputs},
max_favorable_excursion, max_adverse_excursion, return_at_horizon`.
No derived/bucketed columns belong in this table at all — those live in
whatever the analysis layer computes on read, not on write.

## Decision 2 (2026-09-24): recording granularity is 15-minute bars, not 1-minute

**The rule**: every supporting-indicator snapshot and outcome-path
recording (Decision 1) is done on 15-minute bars, not 1-minute.

**Why**: 1-minute bars from 2022-01-01 onward were checked and confirmed
to be a lot of data — roughly 370,000 bars per symbol over ~3.75 years
(390 min/day x ~252 trading days/year), before even multiplying across
symbols or the 28 angles. Beyond the storage/compute cost, 1-minute
resolution is also a *mismatched* granularity for the kind of
must-conditions this system is built around: SMA(5) x SMA(50) crosses
and similar are swing-style signals meant to play out over days, not
seconds. Recording at 1-minute would mostly capture microstructure noise
irrelevant to that timeframe, and would make time-boxed mechanisms like
the grace-window idea nearly meaningless ("wait 10 candles" is only 10
minutes at 1-minute resolution, barely enough time for a slow-moving
indicator like ADX to move at all; at 15-minute resolution it's 2.5
hours, a sensible confirmation window for a multi-day swing setup).
15-minute bars cut data volume ~15x, cut the expensive deep-learning
angle compute cost proportionally, and reduce false near-miss flicker
in the evidence table — with no real loss of relevant signal for
must-conditions operating on this timeframe.

**Caveat carried forward**: if a future must-condition is genuinely
intraday/scalping-style (holding period of minutes, not days), it would
need its own separate recording-granularity decision — this decision
applies to swing-style strategies like the SMA-cross example, not to
every possible strategy this framework might ever host.

## Decision 3 (2026-09-24): one JSON column per supporting indicator/angle, not exploded flat columns

**The rule**: each supporting indicator (each of the 28 angles, plus any
non-angle indicator like ADX or volume-vs-avg) gets stored as **one
column holding its natural output shape as JSON** (a dict), not
flattened into one column per sub-field.

**Why**: angle outputs aren't uniformly shaped — `shock_personality`
returns a flat dict of scalars (`gap_fill_rate`, `vol_persistence`,
`drift_persistence_days`, ...), while `chronos` returns a 5-step-ahead
forecast (`median_forecast`/`p10_forecast`/`p90_forecast`, each a list
of 5 values) plus metadata (`model_backend`, `checkpoint`,
`fallback_reason`). Forcing every angle into flat scalar columns would
mean special-casing vector-shaped angles (chronos and the other
foundation-model angles) differently from scalar ones (shock_personality
and the classic technical indicators) at storage time — exactly the
kind of storage-time decision Decision 1 says to avoid. A JSON column
stores whatever shape an angle naturally produces, with zero flattening
logic at write time, and if an angle later adds a new field (as already
happened for real: `shock_personality`'s `drift_mean_autocorr` was added
after the fact, see its own module docstring), older rows are
unaffected and nothing about the schema needs to change.

**Confirmed consistent with the existing system, not a new invention**:
every angle's `spec.yaml` in `vinu-initial-analysis` already declares its
output as `column: angle_data, type: dict` — this is exactly how angle
results are stored today. This decision just carries that same
already-proven convention into the new evidence table.

**Tradeoff accepted**: the analysis layer (Layer 4 bucketing/quantiles)
can't query a JSON blob's fields as cheaply as a native column — it
needs an explicit flatten/extract step first. This is fine: that
flattening logic belongs in the re-runnable analysis layer per Decision
1, not in storage.

## Decision 4 (2026-09-24): model on/off + per-angle model-selection is a global `vinu-infra` policy, not a per-component setting

**The rule**: whether model-based angles (chronos and the other
foundation-model angles) run at all (`MODELS=false` disables them
entirely, leaving only raw-data and news-based angles/indicators), and
which specific checkpoint/variant each model-based angle uses, is
governed by a single policy living in `vinu-infra` — not duplicated or
decided separately inside `vinu-initial-analysis` or any other
component.

**Why**: `vinu-infra` is already the real, confirmed shared dependency
across components today (imported by `vinu-initial-analysis`,
`vinu-news`, and `vinu-stock-price`), and it already owns the adjacent
shared concern — `vinu-infra/models.py::ensure_model`, the shared model
registry/download logic every model-based angle already goes through.
A global "are models allowed right now" switch and a per-angle
checkpoint override table are one level more global than the existing
per-angle `get_angle_setting()` mechanism (`VINU_<ANGLE>_<SETTING>`,
today living in `vinu-initial-analysis/config.py` and int-only) — so
`vinu-infra` is the correct home, with any per-component override helper
reading from it rather than owning the policy itself.

**Two concrete gaps this decision requires closing** (checked against
real code, not assumed):
1. No angle currently carries a `category` tag (`raw_data` / `model` /
   `news`) in its `spec.yaml` — this needs adding before a `MODELS=false`
   filter can know which angles to skip via the already-existing
   `AngleRunner.run(angle_names=...)` selection mechanism
   (`vinu-initial-analysis/vinu_initial_analysis/runner.py:87`).
2. `get_angle_setting()` only parses integers (`return int(raw)`), and
   `chronos/compute.py`'s `CHECKPOINT` constant is currently hardcoded,
   not wired to any override at all. Per-angle model selection needs
   either a string-supporting sibling setting function, or a small
   dedicated `models.yaml`-style mapping (angle name → checkpoint),
   living in `vinu-infra` alongside `ensure_model`.

## Decision 5 (2026-09-24): moirai, moment, lag_llama are permanently excluded, not just deprioritized

**The rule**: `moirai`, `moment`, and `lag_llama` are kept in the
codebase as-is, but permanently excluded from the supporting-indicators
list and from the `category: model` tagging scheme in Decision 4 —
not merely set to a low priority, and not silently left tagged as
`model` while actually running their fallback.

**Why**: checked each angle's own compute.py — all three are not on a
temporary error-path fallback (like `chronos`'s try/except, which only
falls back if the real pipeline genuinely can't load at runtime). They
are permanently pinned to a `fallback_proxy` by design, documented in
each module's own docstring — `moirai` specifically because its package
(`uni2ts`) requires `torch==2.4.1` while the shared environment is
pinned to `torch==2.13.0+cpu` for every other model-based angle, and
downgrading shared torch to unblock one angle was already judged unsafe.
Feeding a statistical fallback proxy into the evidence table under a
"model" indicator's name would corrupt Layer 4's later analysis: it
would look like an independent, genuinely different model's opinion,
when it is actually just another instance of the same statistical
family already covered by `arima`/`exponential_smoothing`/
`kalman_filters`. The evidence table needs to know what it's actually
looking at.

**What this changes**: `all-possible-supporting-indicators.md` Section A
needs these three struck from the active list (kept visible but marked
excluded, with the reason, not silently deleted) — and the `category`
tagging work in Decision 4 needs a way to represent "permanently
disabled by design" distinctly from both `raw_data` and `model`, so a
future re-enable (once the dependency conflict is genuinely resolved) is
a deliberate, visible decision, not an accidental side effect of
touching the tag.

## Decision 6 (2026-09-24): a startup manifest, living in `vinu-infra`, as the one place to see what a run actually used

**The rule**: build a single summary/manifest, generated at system
startup (or on demand), living in `vinu-infra` alongside the model
policy from Decision 4 — the one place to check "what was actually on"
before trusting a run's evidence data, rather than having to re-derive
it by reading config/env by hand.

**What it reports**:
1. **Angle inventory** — total angles discovered (28 from the current
   directory scan) broken down by `category`: `raw_data` / `model` /
   permanently `disabled` (Decision 5's three exclusions).
2. **Current model policy** — `MODELS=true/false` right now, and, if
   `true`, which checkpoint each model-based angle is actually
   configured to use (once the per-angle override from Decision 4 is
   built).
3. **Active angle count** — how many of the 28 will actually run given
   the current policy (28 minus permanently-disabled, minus the 11 real
   model angles too if `MODELS=false`).
4. **Time format in effect** — which `time_format` recording is actually
   using (Decision 2's 15-minute bars), cross-checked against every
   active angle's own `spec.yaml` `time_formats` list, flagging at
   startup (not silently at runtime) if any active angle doesn't
   actually support 15-minute bars.
5. **Evidence-table column count** — fixed schema columns (`trigger_id`,
   `symbol`, `trigger_time`, must-condition fields, outcome-path fields,
   per Decision 1's schema) plus one JSON column per currently-active
   supporting indicator (Decision 3), reported as a single live number
   (e.g. "9 fixed + 17 indicator columns = 26 total") that changes
   automatically as the model policy changes, rather than being
   hand-counted and going stale.

**Why it lives in `vinu-infra`**: same reasoning as Decision 4 — it's
the one dependency already shared across components
(`vinu-initial-analysis`, `vinu-news`, `vinu-stock-price` today), and
this manifest is a direct reflection of the model policy that already
lives there.

## Decision 7 (2026-09-24): the manifest is versioned, and every run/row stamps which version was active

**The rule**: Decision 6's manifest isn't just a live "what's on right
now" readout — it's versioned (a version id or hash, bumped whenever the
model policy changes: `MODELS` toggled, a per-angle checkpoint changed,
an angle newly disabled). Every recorded run, in every component, stamps
that version onto its own row. This applies system-wide, not just to the
new evidence table from this design — any component's stored result
(`vinu-initial-analysis`'s per-angle runs, the new evidence table, any
future consumer) carries this stamp.

**Why**: checked the real schema this would need to change —
`vinu-initial-analysis/vinu_initial_analysis/storage/meta.py`'s `RunLog`
`runs` table currently has no field at all for "what model policy was
active when this ran" (its columns are `symbol`, `angle_name`, `run_id`,
timestamps, `granularity`, `tier` — nothing about model config). Without
this, two runs of the same angle for the same ticker months apart could
silently be non-comparable — different angle set, different model
checkpoint, `MODELS` toggled in between — and nothing in storage would
reveal that. A live-only manifest (Decision 6 as originally scoped) only
answers "what's true right now," not "what was true when this specific
historical run happened," which is exactly the question that matters
when looking back at a ticker's analysis history.

**Concrete schema change implied**: add a `policy_version` column to
`RunLog`'s `runs` table (and equivalently to the new evidence table's
schema from Decision 1), storing a reference to the manifest version —
not the full manifest duplicated per row, just enough to look it up
later and answer "how many angles ran, with which models, for this
ticker's analysis at that time."

## Decision 8 (2026-09-24): the evidence store lives in `vinu-research`, not a new standalone service

**The rule**: the new evidence table (Decisions 1/2/3) is a new module
inside `vinu-research`, alongside its existing evidence/calibration
stores — not a separate service.

**Why**:
- `vinu-research` already owns every other evidence/calibration store in
  this system (`HypothesisRegistry`, `judgment_store.JudgmentStore`,
  `CalibrationTracker`) — this is the same kind of thing, belongs next
  to its siblings.
- `vinu-research` already owns the analysis machinery Layer 4 will
  eventually need (`sweep_grid.py`'s walk-forward/PBO engine) — same
  service means no cross-service data pull later.
- The wiring pattern already exists and is proven: `vinu-live` already
  pushes real recorded outcomes to `vinu-research` over HTTP today
  (`_record_calibration_outcome` in `feedback_loop.py`). Recording new
  evidence rows follows that same established path — `vinu-live`
  detects the must-condition trigger live (it's already watching the
  market every cycle) and POSTs the indicator snapshot + outcome path to
  `vinu-research`, which owns storage. Nothing architecturally new.
- `vinu-research` already exposes the HTTP surface other components read
  through, so any future consumer (a dashboard, `vinu-strategy`, a live
  Layer-5 lookup from `vinu-live`) goes through the same door everything
  else already does.

**Resolved as a side effect, not deferred**: the "standardized outcome
horizon" question (previously pending) doesn't actually block anything
— Decision 1 already commits to storing the *full outcome path* (max
favorable/adverse excursion, return-at-horizon), specifically so the
"right" horizon doesn't need to be picked before recording starts. The
real analysis of what horizon/R-target to use happens later, at query
time against accumulated rows, and can change without re-recording
anything.

## Decision 9 (2026-09-24): per-ticker coverage is a derived pivot of RunLog, not a new source of truth

**The rule**: the wide, one-row-per-ticker status view (`ticker,
start_date, end_date, models_enabled, {one column per angle}`) is
computed by pivoting `RunLog`'s existing rows on read -- it is not a
separately-written table that could drift out of sync with RunLog.

**Why**: checked what already exists first. `RunLog` already stores
`symbol`, `angle_name`, `analysis_from`, `analysis_until`,
`policy_version`, `status` per row -- everything the wide table needs,
just long (one row per symbol+angle+run) instead of wide. A genuinely
separate, independently-written coverage table would risk the two
disagreeing about the same facts. `vinu-agent`'s `ticker_summaries`
table is the closest existing precedent for "one row per ticker, always
latest" -- but it only stores aggregate `angles_with_data`/`angle_count`
counts and an LLM summary, no per-angle breakdown, no date range, no
model-policy status, so it doesn't already cover this need either.

**What this needed that didn't exist yet**: `RunLog` had `policy_version`
(a one-way hash, Decision 7) but nothing that answers "were models on"
in a directly readable way. Added a real `models_enabled INTEGER` column
(migration, `SCHEMA_VERSION = 3`) alongside `policy_version`, set from
`vinu_infra.model_policy.models_enabled()` at the same two `record_run()`
call sites in `runner.py` that already stamp `policy_version`.

**Where it lives**: `vinu-initial-analysis/vinu_initial_analysis/storage/
ticker_coverage.py::build_ticker_coverage(run_log, symbol, all_angle_names)`
-- pure function, no new storage, reads `RunLog` directly. Exposed via
`GET /analysis/coverage/{ticker}`. "Models enabled" for the ticker as a
whole is reported as the single most recent run's flag, not an aggregate
across mismatched-age angles -- a ticker can legitimately have angles at
different ages under different policies, and blending them into one
number would hide that rather than reveal it.

## Decision 10 (2026-09-24): the must-condition/supporting-indicator recorder runs as angle #29, not a separate live watcher

**The rule**: historical backfill of the signal-evidence table (Phase 2)
runs as a new angle, `signal_evidence`, inside `vinu-initial-analysis`'s
existing angle pipeline -- not as new code inside `vinu-live`.

**Why**: the screener -> download-price/news-for-a-date-range ->
run-every-angle pipeline already exists, already tracks exactly which
date range has been covered per ticker (`RunLog.analysis_from/until`,
now surfaced by Decision 9's coverage view), and already gets triggered
automatically for every ticker the screener discovers
(`vinu-agent`'s `bootstrap_new_tickers`/`discover_new_tickers` ->
`vinu-initial-analysis`'s on-demand `/analysis/run/{ticker}`). Landing
signal-evidence there means backfilling years of historical trigger
events is "run this angle over 2022-01-01 to now," identical to any
other angle, with the date-range bookkeeping already solved for free.
This is a better fit for the BACKFILL problem specifically than a live
watcher would have been -- it does not replace the still-unbuilt LIVE
detector `vinu-live` would need for real-time execution decisions
(Layer 5's continuous lookup), which is a separate concern with a
different rhythm (every cycle, on open positions) from this angle's
(triggered per ticker, over a historical window).

**A real correctness constraint this surfaced**: supporting indicators
snapshotted by this angle must be computed strictly point-in-time from
the bars already in hand -- pulling another angle's stored "latest"
result would silently leak look-ahead bias into historical rows, since
"latest" means "whenever that angle last happened to run," not "as of
the historical trigger moment." So `signal_evidence` computes its own
small set of indicators (ADX, RSI, volume-vs-avg20) directly from bars
rather than reading the other 28 angles' stored outputs. This
limitation is specific to the BACKFILL path; a future live detector
reading other angles' "latest" results for a trigger happening now would
not have this problem, since "latest" and "now" are the same thing
there.

**Implementation**: `vinu-initial-analysis/vinu_initial_analysis/angles/
signal_evidence/` (`category: raw_data`, unaffected by `MODELS`). Walks
bars for every historical SMA(5)xSMA(50) crossing with a complete
forward horizon available, computes the outcome path, and POSTs both to
`vinu-research`'s `SignalEvidenceStore` HTTP routes from Phase 2 --
idempotently (a re-run over an overlapping window treats an
already-recorded `trigger_id` as success, not an error).

## Decision 11 (2026-09-24): coverage columns are three-valued (real status / pending / not_required), not a bare present-or-absent

**The rule**: `build_ticker_coverage`'s per-angle column is never just
"has data or doesn't." It's one of three things: the angle's real latest
status (it has run), `"pending"` (required under the CURRENT model
policy, hasn't run yet -- a real gap), or `"not_required"` (excluded by
current policy -- a `category: model` angle while `VINU_MODELS_ENABLED`
is false, or one of Decision 5's permanently-disabled three; its absence
is correct, not a gap). An overall `overall_status` field
(`"pending"`/`"completed"`) is derived the same way: `"completed"` means
every currently-required angle has run, not merely "nothing left
pending" — an empty required set with zero real data still reports
`"pending"`, since `"completed"` needs positive evidence, not the
absence of a gap.

**Why**: without this, a models-off ticker would show every model-
category angle as a bare gap indistinguishable from a genuine unmet
requirement, making every models-off ticker look permanently incomplete
regardless of how much real, correctly-scoped work had actually been
done. The screener (or any consumer) needs to be able to check "is this
ticker done" with a single field, without first having to separately
know the current model policy to interpret an empty column correctly.

**One rule that keeps this honest**: real data always wins over the
`not_required` label. An angle that genuinely ran before models were
later turned off keeps showing its real recorded status, never gets
silently overwritten by `not_required` -- that label only explains an
absence, it never erases real history.

**Implementation**: `build_ticker_coverage` now takes the full angle
roster (`AngleRunner.list_angles()`'s own shape: `{name, spec}`, spec
carrying `category`) instead of a bare name list, and calls
`vinu_infra.system_manifest.resolve_active_angles` -- the exact same
function Phase 1's model-policy filtering in `AngleRunner.run()` already
uses -- rather than re-deriving the required/not-required split a
second, possibly-inconsistent way.

## Decision 12 (2026-09-24): every workable supporting indicator gets wired before Phase 3, not a curated subset

**The rule**: rather than hand-picking a "reasonable" subset of
supporting indicators to implement, every candidate identified as
computable from bars alone (Section H/I of
`all-possible-supporting-indicators.md`) gets wired into
`signal_evidence/compute.py`, full stop — including indicators that
didn't exist in `vinu_tools` yet (built there first as real modules,
never hand-rolled inline) and `vwap_dist` (which needed a real design
decision, not just a formula, before it could be wired).

**Why**: this follows directly from Decision 1's own reasoning —
hand-picking which indicators "should" matter is exactly the kind of
bias the whole design is trying to avoid; Layer 4's future analysis is
what's supposed to decide which indicators separate winners from losers,
not a human guessing up front which ones look promising. Stopping at a
"reasonable-looking" subset (the original ADX/RSI/volume-vs-avg20, or
even the first expansion pass) would have silently reintroduced that
bias at the recording layer instead. The origin was a real bug report,
not a feature request: `06-mistake-duplicated-indicator-logic.md`
started as "ADX/RSI were hand-rolled instead of reusing `vinu-tools`",
and the fix for that bug surfaced the fact that most of Section H/I was
already sitting unwired in a real, tested library — so the natural
extension of fixing the bug was finishing the whole column list per this
decision, not stopping once the original two were fixed.

**What this added**: 48 more supporting indicators beyond the original 3
(51 total), four new real `vinu_tools` modules (`ichimoku`,
`parabolic_sar`, `mfi`, `accumulation_distribution_line` — `vinu_tools`
is now a 28-indicator library, up from 24, with every place that
hardcoded "24" found and corrected), and a real design decision for
`vwap_dist` (session-slice bars by UTC calendar date from `bar_ts`
before calling `vinu_tools`' cumulative-since-first-bar `vwap` module
independently per slice, since this angle has no exchange-local
trading-session machinery). Full account, including the real
configurability bug caught and fixed along the way (the multi-output
`vinu_tools` modules silently ignoring a period override when called via
the "return every column at once" optimization), is in
`06-mistake-duplicated-indicator-logic.md`.

**What this does NOT change**: Phase 3 (Layer 4's analysis/bucketing
layer) is still deliberately deferred — more columns recorded per
trigger doesn't create real accumulated rows to bucket against any
faster; that still needs live/backfill time to pass.

## Decision 13 (2026-09-24): the manifest is exposed at `GET /analysis/manifest` in `vinu-initial-analysis`, unauthed, always-live, unversioned

**The rule**: `04-pending-manifest-http-endpoint.md`'s four open
questions, settled:

1. **Which service owns the route?** `vinu-initial-analysis`, via its
   existing `routes_read.py` — the same file `GET /analysis/coverage/
   {ticker}` already lives in, following the exact same thin-route
   pattern (`svc.list_angles()` for the angle list, delegate everything
   else to the already-tested `build_manifest()`). This is the ONLY
   place the manifest is exposed — `vinu-live`/`vinu-research` needing
   "is MODELS on right now" call out to this one route rather than each
   getting their own copy, same reasoning as Decision 9's "derived pivot,
   not a second copy" applied to routes instead of storage.
2. **Auth**: none beyond whatever the rest of `routes_read.py` already
   has — confirmed directly by reading the file: not one of its existing
   routes (`/angles`, `/coverage/{ticker}`, `/story/{ticker}`, etc.) has
   an auth dependency today. The manifest reveals model-policy state, not
   trading data, so it doesn't warrant being the one route in this file
   that's suddenly stricter than its neighbors.
3. **Caching**: none — always live. `build_manifest()` is pure
   computation over an already-in-memory angle list (confirmed cheap,
   same cost profile as `/coverage/{ticker}`, which already recomputes
   its own pivot fresh on every call with no caching).
4. **Response shape stability**: unversioned, same posture as every
   other route in this file — internal tooling, shape can move if
   `build_manifest()`'s own return shape ever changes. No separate
   contract to maintain.

**Why now, not deferred further**: all four questions turned out to have
an existing, already-established answer elsewhere in this same
codebase (Decision 9's routing precedent, `routes_read.py`'s own real
auth posture, `/coverage/{ticker}}`'s own no-caching precedent) — there
was no genuinely new architectural decision left to make once each
question was actually checked against real code, only a should-copy-
the-existing-pattern check.

**Implementation**: `GET /analysis/manifest` in
`vinu-initial-analysis/vinu_initial_analysis/server/routes_read.py`,
calling `vinu_infra.system_manifest.build_manifest(svc.list_angles())`
directly — `svc.list_angles()` already returns exactly the shape
`build_manifest()` expects (confirmed by reading both signatures: `list
[dict]` with `name`/`spec`, the same object `/angles` and
`/coverage/{ticker}` already pass around).

## Decision log (pending / to be added next — deliberately left open, not blocking)

- The analysis-layer design (Layer 4): quantile-based bucket edges,
  cluster-robust weighting via `shock_clustering`, minimum-sample
  gating with a coarser-bucket fallback, and full win/loss distribution
  output — as discussed in `00-explanation.md`. Deliberately not
  decided yet — there's no real accumulated data to test candidate
  bucketing methods against until Phase 2 (the recording layer) has been
  running for a while. To be revisited once real rows exist, not before.
