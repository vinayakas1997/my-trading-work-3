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
- `vinu-portfolio`'s circuit breaker computes `halve`/`flat` actions —
  nothing consumes them (item #23).
- A second risk-tiering system is exposed via an API nobody reads (item
  #23).
- `vinu-live`'s main execution loop doesn't call risk-limit checks at
  all — the most serious of these, since it's the layer touching real
  money (item #24).
- Same-symbol conflicts between strategies aren't netted anywhere from
  `vinu-portfolio` through to `vinu-live` (item #23/#24).

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

## Why these are jotted down together, not solved together

These five are genuinely different in scope and dependency order — #1
and #2 can be discussed now, #4 depends on Phase 3/Track 2 aggregate mode
existing first, #3 raises a real trust/tagging question before any code
gets written, and #5 is closest to the already-known "live detector"
gap. Recording them here means none of them get lost or have to be
re-explained later, without forcing a decision on any of them before
they've each been thought through on their own.
