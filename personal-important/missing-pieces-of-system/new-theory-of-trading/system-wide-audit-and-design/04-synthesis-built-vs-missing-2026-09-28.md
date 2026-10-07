# Synthesis (2026-09-28): what's built vs. what's still missing, read end to end

This file is a plain-language synthesis produced by reading, cover to
cover in one pass, `high-expectations/chatgpt-version/already-built.md`
(the trading-philosophy checklist cross-checked against real code) and
this folder's own audit series — `00-overview.md`, `01-full-system-layer-map.md`,
the 26-item `02-open-questions-strategy-and-simulation.md`,
`03-strategy-definition-full-schema.md`, and `reverse-engineering/`. It
adds no new findings of its own; it's a consolidated answer to "just go
through and tell me," kept as a file per instruction rather than left
only in chat, since this folder's own standing rule is that everything
here is meant to be read and acted on later, not summarized away and
lost.

## What's actually built and working

Almost everything the "how he trades" philosophy in
`already-built.md` asks for exists as real code, not just design:
regime/trend/news/correlation/pattern-matching angles, a multi-agent
brain with a hard risk gate between AI and the broker, a structured
`TradeScore` (regime fit + EV + risk/reward, self-calibrating), VWAP/TWAP
execution, a real kill switch, portfolio correlation-aware sizing, decay
detection, a full audit trail, and a post-trade reflection loop. The
live-decision re-evaluation loop (`vinu-live/live_decision/`) was
reverse-engineered and built end-to-end during this same audit series,
closing two critical gaps along the way (no risk-limit check on the main
execution loop; no same-symbol netting across strategies). Full detail
and citations are in `already-built.md` itself — this file doesn't repeat
its "Fully built" list line by line.

## The real, still-open gaps

**1. Item #26 is the one to read first** — it's the audit's own direct
answer to "is everything properly connected," and it's **no**. Not
because components are badly built, but because the *seams between them*
are broken:
- Track 1's must-condition evidence and the research loop's discarded
  generation candidates don't all feed one place — three separate
  evidence streams, none unified (item #21, #26).
- `vinu-reflection`'s findings sit in their own store; the "step-8
  synthesis agent" that would read across all of them and connect the
  dots is designed but explicitly not built (item #25.4).
- Indicator math (ADX/ATR/RSI) is independently reimplemented in 4+
  places — two confirmed to have had real formula bugs (item #20), one
  instance deliberately left un-reconciled because it's a persisted KNN
  feature library that can't silently change formulas without breaking
  historical comparability.
- Ticker discovery is a static seed list, not `vinu-screener`'s live
  output — the pipeline's entry point isn't actually live (item #16.5).

**2. Genuinely undesigned/unbuilt items:**
- **Item #4** — the simulator's PnL sizing doesn't consume Track 2's
  ATR/evidence-confidence engine, so backtests report abstract
  Sharpe/win-rate, not real dollar expectancy. Blocked on Track 2's
  aggregate mode existing first.
- **Item #5** — there's no "present-data" recording layer for
  live/current data mirroring how pre-analysis stores historical angle
  output. Entirely undesigned; a concrete `live_snapshots` schema is
  sketched in the item itself but not built.
- **Item #10** — cross-track disagreement (Track 1 fires, Track 2 sees
  no move, or the opposite) isn't captured as its own signal. Not
  designed yet.
- **Item #16** findings #3 and #5 — no unified "candidate graveyard"
  across the three places an idea can die, and ticker discovery is
  seed-and-forget rather than a live loop.
- **Evidence-confidence sizing factor** — named repeatedly as part of
  composite position sizing, but a fresh grep confirmed it has no code
  sketch anywhere (a correction to an earlier wrong claim that it was
  "already sketched").
- **Exit mechanism for `live_decision`-opened positions** —
  investigated, confirmed real, deliberately not built pending explicit
  go-ahead given live-money stakes.

**3. Explicitly deferred (not gaps, decisions):** order-book/L2 depth
(paid-tier blocker on both Alpaca and Polygon), on-chain crypto data (no
crypto execution exists yet to consume it).

## The one thing worth flagging directly

The audit's own conclusion in item #26 is the most senior-quant-relevant
finding here: this is a collection of well-built individual components,
but "the plan" — the connective tissue between them — is the part still
mostly missing or silently unenforced. That's not a discouraging read,
it's the finding: exactly why auditing layer-by-layer before building
anything new on top of this was worth doing. This audit series *is* the
new-theory-of-trading system's own connecting work, and items
#1/#10/#21/#26 are exactly where it still doesn't reach.

## Follow-up (2026-09-28): the exit-mechanism gap, built

Picked as the first item to build off this synthesis, on explicit
instruction given the live-money stakes. Tracing the code before
building surfaced something worse than "no exit mechanism exists": the
existing `applied`-once semantics in
`LiveScheduler._fetch_live_decision_weights` meant a live_decision
position was liable to be force-closed by `SignalTranslator`'s own
"held but not targeted -> close" rule the very next cycle after opening,
not held indefinitely as `reverse-engineering/02-implementation-status.md`
had previously stated -- no test had ever exercised a second cycle, so
this had never actually fired, but was live, untested risk. Fixed by
making `live_decision_open_positions` (new table) the source of truth
`LiveScheduler` re-reads every cycle, plus a periodic HOLD/EXIT review
cadence that re-invokes the same `live_decision_agent` team (mode=
"review", new prompt section) rather than a second agent. Full detail,
citations, and test counts are in
`reverse-engineering/02-implementation-status.md`'s own 2026-09-28 entry,
kept there rather than duplicated here since that file is this series'
existing single source of truth for what's built.

## Follow-up (2026-09-28): live ticker discovery, built

Picked as the next item to build. `vinu-agent/vinu_agent/cli.py`'s
`planner_worker_main` already had an opt-in `screener_ranker_id`
mechanism, but it only ever ADDED tickers to `TickerSummaryStore` once
(bootstrap) — the per-cycle watchlist itself was still
`list_summaries()`'s full, ever-growing accumulation, i.e. still
seed-and-forget in substance even though a screener integration existed.
Fixed: when a ranker is configured, the screener's *current* top-ranked
output (intersected with what's actually bootstrapped, so a ticker still
mid-bootstrap isn't half-processed) is now the real per-cycle source,
with the static seed list staying additive on top as the human override.
Unset or a transient fetch failure falls back to the old accumulation
unchanged. Full detail, the named consequence (an unranked ticker stops
being refreshed each cycle), and test counts are in
`02-open-questions-strategy-and-simulation.md`'s own item #16 finding #5
UPDATE (2026-09-28), kept there as this series' existing source of truth.

## Follow-up (2026-09-28): unified candidate graveyard, built

Picked as the next item to build. A research idea can die at three real,
disconnected points in `vinu-research`: generation-time (heuristic
ranking discard), sweep-time (a failed backtest point), or hypothesis-
level rejection — each already durably recorded in its own store, but
with no way to ask "has something like this already failed, and why"
across all three at once. Built as a read-time query
(`candidate_graveyard.py`), not a fourth table — none of the three
existing stores changed. New `GET /research/candidate-graveyard/{symbol}`
returns one combined, time-ordered list tagged by source. Deliberately
left open: linking a generation-time code_hash to a later sweep failure
of "the same" candidate (a real, separate join decision), and wiring
this query into generation-time dedup as a blocking gate (kept as a read
surface, not a new policy). Full detail and test counts are in
`02-open-questions-strategy-and-simulation.md`'s item #16 finding #3
UPDATE (2026-09-28).

## Follow-up (2026-09-28): present-data live snapshot layer, built

The last of the three ready-to-build items from this file's original
list. Built to the exact concrete schema item #5's own text already
specified: a new append-only `live_snapshots` table (mirroring
`vinu-initial-analysis`'s `RunLog`, but keyed on real wall-clock
recency rather than a historical range), written by
`vinu_live/live_decision/poller.py` — the one place in this codebase
that already computes a real live indicator snapshot — and read via new
`GET /live/snapshots/{symbol}` (latest per angle, with
`staleness_seconds` computed fresh at request time, never stored) and
`GET /live/snapshots/{symbol}/{angle_name}/history`. Honestly scoped:
this gives one real angle (`live_indicators`) a live-data home, not all
30 of `vinu-initial-analysis`'s historical angles — building a live
equivalent for each of those would be separate, much larger work per
angle. Full detail and test counts are in
`02-open-questions-strategy-and-simulation.md`'s item #5 UPDATE
(2026-09-28).

This closes out all three items this synthesis file originally flagged
as ready to build (exit mechanism, live ticker discovery, unified
candidate graveyard, present-data snapshots — four, counting the exit
mechanism picked first). Remaining open items from the parent audit are
listed in this file's own "Genuinely undesigned/unbuilt items" and
"Blocked or needs a design decision first" sections above.

## Follow-up (2026-09-28): precondition write-back path (point 6), built

Continuing past this file's original three items, into the broader
remaining-open-items list. Point 6 of the reverse-engineering series
(`precondition.tested`/`precondition_held`) had schema fields but no real
writer. Built: a new `PreconditionStateStore` (`vinu-strategy`) as a
separate SQLite table, deliberately NOT written back into the strategy's
own YAML file (a human-authored source of truth, reloaded on its own
schedule) — overlaid onto `GET /strategy/strategies/{name}`'s
`precondition` dict at read time instead. New
`POST /strategy/strategies/{name}/precondition-check`, called by
vinu-live's poller on every real EXECUTE/SKIP `live_decision_agent`
verdict (both count as "tested" — being checked and failing is still
being tested). Found and fixed a real, pre-existing test-isolation gap
along the way: `routes_read.py`'s `_get_api()` singleton is never reset
between tests, which a first version of this build's own route test
broke `test_merged_app.py` with, depending on run order. Full detail and
test counts are in `reverse-engineering/02-implementation-status.md`'s
point 6 log entry (2026-09-28). Point 6 is now fully closed.

## Follow-up (2026-09-28): item #22 finding #3, point-in-time safety at the strategy layer, built

Continuing further into the remaining-open-items list. Traced the
finding's two upstream call paths before touching anything: the
correlation/angle path is backed by `vinu-initial-analysis`'s
already-`analysis_until`-pinned rows (a different, untouched question),
but the features path (`vinu-tools`, live-computed from candle data) had
**zero** point-in-time enforcement — always "last 60 days from
wall-clock now, whenever the HTTP call happens to fire." Fixed by
reusing the already-built `clamp_to_as_of()` machinery (item #21 pattern
#1): a new `as_of` param threads from `POST /strategies/{name}/evaluate`
through `StrategyService.evaluate()` (captured once per run, not
per-symbol, so every symbol in one run shares the same decision-time
instant) through `FeaturesClient` to vinu-tools' feature route to
vinu-stock-price's own enforcement. Defaults to wall-clock now,
unchanged behavior for every existing caller. Full detail and test
counts are in `02-open-questions-strategy-and-simulation.md`'s item #22
finding #3 UPDATE (2026-09-28).

## Follow-up (2026-09-28): item #4's evidence-confidence sizer, built (item #10 still open)

Went after items #4 and #10 together since both were blocked on the same
missing piece: no computed "how much should this symbol's historical
evidence be trusted" number existed anywhere. Built it once, shared, per
this series' own "reduce, don't rebuild" discipline:

- `vinu_infra/evidence_confidence.py` (new, shared) — point-in-time-safe,
  Laplace-smoothed confidence math, callable by any service without
  duplicating the formula.
- `vinu-research`'s `compute_track2_aggregate()` + new
  `GET /research/track2-aggregate/{symbol}` read it from
  `SignalEvidenceStore` (Track 1's already-recorded trigger outcomes —
  Track 2 itself is still design-only, but the raw evidence it would need
  already exists and was sitting unused per the store's own docstring).
- `vinu-simulator`'s new `EvidenceConfidenceSizer` (`engine/sizing.py`)
  consumes it — the first sizer in that file to scale per-symbol rather
  than by one portfolio-wide factor, deliberately built with **no network
  calls of its own** (evidence data flows in through
  `SimulationInput.evidence_triggers`, pre-fetched by the caller, matching
  every other sizer's "act only on data already handed to it" discipline).

This closes item #4's stated blocker for real (confirmed via a fresh grep
that the earlier "already sketched" claim about `EvidenceConfidenceSizer`
was wrong — there was no code before this). Item #10 is **not** closed:
it needs a `MoveEvidenceStore` that still doesn't exist, plus its own
reconciliation job comparing that against this new confidence number —
real, separate work. Also left open, honestly: no caller in this codebase
yet populates `SimulationInput.evidence_triggers` for a real backtest run
— that wiring (which job fetches evidence and passes it in) is a small,
separate integration task in whatever orchestrates `vinu-research`'s
sweeps, not built here. Full detail and verified test counts (vinu-infra
334 passed, vinu-research 1149 passed, vinu-simulator 262 -> 274 passed
via `git stash` before/after check, 0 regressions anywhere) are in
`02-open-questions-strategy-and-simulation.md`'s item #4 and item #10
UPDATE (2026-09-28) entries.

## Follow-up (2026-09-28): item #10, cross-track disagreement, built (scoped down on purpose)

Discussed the original 4-state `cross_track_check` sketch directly before
building it and cut it down: what was actually wanted was catching
`track2_only` (a real move nothing was watching for) specifically, without
standing up a second continuous scanning system to do it.

- Track 2's move check (`detect_move()` — the codebase's own already-
  documented "2xATR(14)" floor) now runs inside `vinu-live`'s poller on
  every candle close for every watched (ticker, timeframe) pair,
  unconditionally — not gated behind any strategy's must-condition firing,
  which is what makes `track2_only` representable at all. No new scanner:
  this piggybacks on the exact loop item #5 already hooked into.
- New `MoveEvidenceStore` (vinu-research, sibling of `SignalEvidenceStore`)
  records only real detections. New `list_unconfirmed_moves()` is a
  read-time join against `SignalEvidenceStore` — matching this codebase's
  own established pattern for this kind of cross-store question, not a
  new stored/periodic table.
- Surfaced honestly, not hidden: nothing in this codebase actually writes
  to `SignalEvidenceStore` in production yet (confirmed by grep — only a
  read-only agent tool references it). That's a separate, pre-existing
  gap. Until it's fixed, most/all real moves will show as `track2_only`
  by default, which is a true reflection of current state, not a defect
  in this build.
- Test counts and full reasoning are in
  `02-open-questions-strategy-and-simulation.md`'s item #10 UPDATE
  (2026-09-28, second pass). vinu-live 571 passed, vinu-research 1163
  passed, 0 regressions in either.

Both items #4 and #10 from this file's "genuinely undesigned/unbuilt"
list are now closed (with the honest caveats above, not silently glossed
over).

## Follow-up (2026-09-28): item #14A factor #2, regime-aware sizing, built

Continuing down item #14A's composite-sizing recommendation. Factor #1
(evidence-confidence) was item #4, above; factor #2 (regime-aware) was
next in line since `engine/regime.py`'s classifier already existed,
point-in-time-safe and tested, and simply had no sizer reading it.

New `RegimeAwareSizer` scales the whole portfolio (not per-symbol, unlike
the evidence sizer -- regime is a benchmark-level classification) by a
factor looked up from the current bar's regime label. The real find
here: `vinu-simulator`'s service layer was already fetching a benchmark
ticker's price series for post-hoc regime-attribution reporting after
every run finished -- it just never got threaded into the run itself.
Wiring it in was mostly "use data already being fetched," not new
plumbing. 13 new tests, full suite 274 -> 287 passed (verified via `git
stash`), 0 regressions. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #14A factor #2
UPDATE (2026-09-28).

Factor #3 (drawdown-aware) remains open -- confirmed earlier in this
series as *not* a drop-in (`PortfolioDrawdownMonitor` is built for live
polling against a running agent API, not a pure backtest-callable
function; the pure threshold logic would need extracting first, real
separate work). Factor #4 (correlation-aware) was already built before
this session as `CompositeSizer`.

## Follow-up (2026-09-28): item #11 finding #4, per-turn tool caching, built

Checked all five of item #11's findings before touching anything —
findings #1 (shared date-util module), #2 (as-of clamp test coverage for
the two priority files), #3 (fundamentals retry), and #5 (options 429/401
distinction) all turned out to already be fixed, verified by reading the
actual code rather than trusting the audit's original text. Only finding
#4 (no per-turn caching) was still real.

New `CallCache`, added to `stock_price_tool`/`news_tool`/`options_tool`/
`fundamentals_tool`, scoped to each tool instance's own lifetime (a fresh
instance per run, per `build_registry()`) so it can never leak a stale
response across replay instants or sessions. Errors and options'
"empty" result are deliberately never cached, so a later identical call
in the same run can still retry. 11 new tests, full vinu-agent suite
1462 -> 1473 passed, 0 regressions. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #11 finding #4
UPDATE (2026-09-28).

## Follow-up (2026-09-28): item #11 finding #2 cleanup, 7 of 8 remaining zero-coverage tool files closed

Rounded out finding #2 right after finding #4: six small, mechanical
tool files (session search, skill loading, workflow planning/completion,
compaction, and the angle-cluster data module itself) plus
`position_sizing_tool.py`'s wrapper logic (the underlying sizing formula
already had its own tests). 27 new tests, vinu-agent 1473 -> 1500 passed,
0 regressions. Left `trade_plan_tool.py` (1330 lines) explicitly open --
real, substantial work on its own, not a same-pass mechanical add.

## Follow-up (2026-09-28): item #14A factor #3, drawdown-aware sizing, built

The last of item #14A's four sizing factors. Confirmed with a direct
question first (the real design decision this one needed): the
ok/halve/flat/halt action ladder maps to size multipliers `1.0/0.5/0.0/
0.0`, matching the live system's own stated intent literally, and halt
is not sticky -- a later recovery returns to whatever rung the ladder
currently sits at.

The actual blocker named in the audit ("not a drop-in" because
`PortfolioDrawdownMonitor.update()` fires a real HTTP halt call) turned
out to be a small, surgical fix: extracted the pure threshold/action math
into `compute_drawdown_action()` (no HTTP, takes/returns peak/start
explicitly), which the live monitor now delegates to unchanged (17
pre-existing tests still pass byte-for-byte) and a new
`DrawdownAwareSizer` in vinu-simulator also calls -- one formula, two
callers, never two independently-derived drawdown policies to drift apart
again.

25 new tests total (10 vinu-portfolio, 15 vinu-simulator), 0 regressions
in either suite. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #14A factor #3
UPDATE (2026-09-28).

All four of item #14A's composite-sizing factors are now accounted for:
#1 evidence-confidence, #2 regime-aware, #3 drawdown-aware -- all built
this session -- and #4 correlation-aware, which already existed as
`CompositeSizer` before this audit series started.

## Follow-up (2026-09-28): item #21 pattern #2, indicator-duplication cleanup, closed

Went through all four originally-named instances of the duplicated-
indicator pattern before building anything -- three turned out to
already be fixed (Track 1's original, `vinu-screener`'s deliberate
non-fix, and `trend_lifecycle`'s true-range, contrary to an older audit
note claiming it was still untouched). Only `vinu-stock-price`'s
`query/indicators.py` was genuinely still hand-rolling SMA/RSI/MACD/
volatility/ADX.

The "real data-migration decision" flagged when this item was first
raised turned out not to apply: this module computes indicators fresh on
every API call and never persists them (confirmed -- the only DB
involved is an in-memory, per-request DuckDB connection for joining raw
prices), so there was no historical seam to manage. Swapped it to
delegate directly to `vinu-tools`' shared `compute(rows, name=...)`
functions -- every hand-rolled helper in the file is gone. 4 new tests,
including two asserting the output is numerically identical to calling
`vinu-tools` directly (real delegation, not a second implementation that
happens to agree). Full vinu-stock-price suite 139 -> 143 passed, 0
regressions. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #21 pattern #2
UPDATE (2026-09-28).

Still open: item #20.6's actual root-cause fix (making
`get_indicator_module()` the one documented, blessed import path) --
every instance of this pattern was fixed one at a time, not by removing
the reason a 5th instance could still happen the same way.

## Follow-up (2026-09-28): Step 9, a real consumer for the reflection brain, built

Confirmed which consumer to wire first before building: Planner/vinu-agent,
the lowest-risk of the three named consumers since it doesn't place
orders itself. `vinu-reflection` gets its first-ever HTTP surface (it
was worker-loop-only by deliberate original design) -- a genuinely
new `serve` command, not a retrofit -- exposing the brain's already-
durable synthesis output read-only. `vinu-agent`'s new
`get_reflection_synthesis` tool reads it over plain HTTP, no in-process
option, since the circular-dependency problem this whole finding exists
to avoid runs in both directions (vinu-reflection already imports
vinu-agent).

Honest note worth keeping: "Planner" isn't one findable AGENT.md file in
this codebase -- it's `planner_worker_main`'s triage logic, which hands
off to the **research** team once triage says yes. Wired the new tool
into that team's `idea_generator` agent as the closest real match, not a
perfect one-to-one to the design doc's own naming.

13 new tests (vinu-reflection) + 4 (vinu-agent), 0 regressions in either.
As a side effect, vinu-reflection's full test suite now runs cleanly in
this environment for the first time this series (192 passed) -- it
couldn't before. Full detail in
`02-open-questions-strategy-and-simulation.md`'s Step 9 UPDATE
(2026-09-28).

Deliberately not built: the other two named consumers
(risk_gatekeeper/vinu-live, capital_allocator/vinu-portfolio) -- the same
read-only endpoints already serve them, just not wired yet.

## Follow-up (2026-09-28): policy_version/schema-version threading, built for one hop

Cleared a naming trap before building anything: `vinu_infra.model_policy
.policy_version()` already exists, but stamps which ML model
checkpoint/config is active -- a different question than this item asks
about (a schema-drift guard on the agent<->research<->simulator request
chain). Built a separate mechanism, `vinu_infra.contract_version
.contract_version()`, rather than conflating the two.

Confirmed approach directly: a deterministic hash of the pydantic
model's own schema, not a manually-bumped version int, so it can't be
forgotten. Discovered a real architectural constraint while building --
no service in this codebase imports another's pydantic models at
runtime in production code (only in tests), so a "sender computes and
sends its own version" design doesn't fit. Resolved by having the
*receiving* service (which always has its own model in-process) echo
its live schema version on every real response, and pinning that value
in the existing import-based contract test -- so a real shape change
fails a test loudly, not silently, the moment it happens.

Scoped to the research<->simulator hop as one complete, tested slice;
the agent<->research hop is the same pattern, left as a fast follow.
9 new tests across three services, 0 regressions. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #17 UPDATE
(2026-09-28).

## Follow-up (2026-09-28): the SignalEvidenceStore writer gap, closed

The last item on today's list -- found honestly, not hidden, while
building item #10: `SignalEvidenceStore` has always had a store and a
route, but nothing in this codebase ever actually wrote to it in
production. The real blocker was naming, not plumbing: the store needs
a string name per must-condition, but the real implemented condition
format is a structured `{source, key, operator, value}` dict with no
name field at all.

Confirmed directly: auto-derive the name from the condition's own
fields (`live_indicators.adx_14_gt_999`) rather than require hand-
editing every strategy's YAML with a new field. `vinu-live`'s poller now
writes a real trigger exactly once per genuine must-condition firing,
best-effort, same fail-safe posture as this session's other writers. 9
new tests, vinu-live 571 -> 580 passed, 0 regressions.

This closes the loop on item #10 too: `list_unconfirmed_moves()` was
built against this store but had nothing real to reconcile against
until now -- it can finally distinguish a genuine `track1_only` case
from `track2_only`, instead of everything defaulting to unconfirmed.

This closes out every item from today's session, including the ones
found along the way rather than planned at the start. Full detail in
`02-open-questions-strategy-and-simulation.md`'s item #16 finding #1
UPDATE (2026-09-28).

## Suggested next step

Pick one open item and turn it into an actual implementation plan.
Candidates ranked by leverage: item #10 (cross-track disagreement as its
own signal) or the evidence-unification piece spanning #1/#21/#26, since
those are the highest-leverage "seam" fixes rather than net-new features.
