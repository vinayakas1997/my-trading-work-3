# What the existing data already lets us build — twenty-five cross-package analyses

## Context

This came out of a follow-up conversation to
`maturity-agentic-system-explanation.md` (same parent folder). That doc
answers "how does a maturity signal get computed and consumed." This doc
answers a different, earlier question: **given everything the system
already writes to disk — cataloged in full in
`project-understanding/05-full-recorded-information/README.md` — what
genuinely rich analysis is already sitting there, unbuilt, requiring no
new instrumentation?**

The honest starting observation from that data-inventory doc: roughly a
third of the ~55 cataloged stores are write-only today. Some of that is
"built ahead of a consumer that doesn't exist yet" (deliberate — see
`ticker_daily_snapshots`, `AllocationHistoryStore`,
`CorrelationMonitorStore`). But the deeper opportunity isn't those —
it's that almost every signal needed for rich, cross-cutting analysis is
already being written *today*, just fragmented across seven packages
that never join against each other. The eight analyses below are not new
telemetry. They are joins across data that already exists.

Each one is deliberately scoped bigger than a single scalar gate — the
guidance behind this pass was explicitly not to self-limit to "what's
minimal" but to think about what's genuinely adequate given how much
real data already exists at every corner of this system.

---

## A. Angle intelligence — which of the 29 forecasting angles actually earn their keep, and where

**Join**: `angle_calibration_entries` (Brier score, directional
correctness, per angle) × `decay_snapshots` × `ticker_daily_snapshots`'
historical `angle_digest` × `regime_tag` on the artifacts those angles fed.

**What it buys**: not just today's `calibration.py` global
`low_trust < 0.45` flag per angle, but a full **trust trajectory per
angle, per regime, per ticker cluster, over time**. This catches an angle
that *used to be* reliable quietly decaying (concept drift) before it
drags a live decision down with it, catches an angle that's only ever
been validated in one regime pretending to be general-purpose, and
builds a genuine "which angles do I actually trust, and under what
conditions" map instead of one global scalar per angle.

## B. Regime × strategy coverage map — where the system has real evidence vs. is flying blind

**Join**: `regime_tag` (on `artifacts`) × `bench_history` ×
`decay_snapshots` × `trade_audit_log.jsonl` entries, cross-tabulated as
strategy-type × regime × realized outcome.

**What it buys**: an actual coverage density map, not a single maturity
tier. Not "the system is early_live" but "the system has real, decent
evidence for momentum strategies in low-vol regimes, and essentially
zero evidence for mean-reversion in high-vol regimes." This is a
materially more useful thing for the Planner, `risk_gatekeeper`, or a
future narrating agent to consult than one global number — it tells the
consumer exactly *where* to be more cautious, not just *how much*
caution to apply everywhere uniformly.

## C. Money-flow / execution intelligence — why trades actually lose, broken down by decision context

**Join**: `trade_audit_log.jsonl`'s `slippage_stats()`, `loss_cause`,
`trade_score_tier`, and `risk_band` at entry.

**What it buys**: today this is one aggregate TCA number behind one API
route (`GET /live/tca/slippage`). Joined against the decision context
that produced each trade, it answers real questions: do specific
trade-score tiers systematically get worse fills? Does a specific
`risk_band` correlate with a specific `loss_cause`? This turns execution
data from a compliance/reporting artifact into a genuine "which of our
own decisions predict bad outcomes" model — a feedback signal that
closes the loop from *how* a trade was decided back to *why* it lost
money, not just *that* it lost money.

## D. Decision-process intelligence — does *how* the LLM decided predict *whether* it was right

**Join**: `llm_calls.db` (vinu-agent) and `telemetry.db` (vinu-infra) —
today both 100% write-only, zero production readers — joined against
realized trade outcomes and `risk_gatekeeper` verdicts.

**What it buys**: a completely novel signal nobody has looked at yet.
Does a forecast made after a retry (`retry_count > 0`, indicating a
flaky or malformed first response) underperform one that succeeded
cleanly? Does latency or `token_count_source` correlate with a later
`risk_gatekeeper` rejection? This uses *process metadata about how
confidently and cleanly the LLM produced a call* as a leading indicator
of decision quality — independent of the content of the call itself.
Two stores that exist purely as forensic logs today become a real
predictive signal once joined to outcomes.

## E. Cross-package systemic risk — the slow-boil pattern no single cycle can see

**Join**: `CorrelationMonitorStore`'s per-cycle flags (vinu-live) ×
`AllocationHistoryStore`'s per-strategy `vol_annualized` and sleeve
composition (vinu-portfolio) × `decay_snapshots` (vinu-research).

**What it buys**: these three currently never meet. Joined over weeks,
they can reveal concentration risk *building up gradually* even when no
single cycle's correlation check ever crosses its own threshold — a
genuinely different class of insight than "is this pair correlated right
now." This is exactly the kind of pattern a per-cycle check is
structurally blind to, because each cycle only ever looks at itself.

## F. Human-in-the-loop as a measured variable, not an assumed good

**Join**: `significance_flags`' `response_rate()`, `resolved`,
`response_text` × Thesis Intake's human-sourced theories in
`HypothesisRegistry` (`vinu_research/hypothesis_registry.py`, real,
lock-protected `hypotheses.json` — genuinely not in the 55-store catalog
at `project-understanding/05-full-recorded-information/README.md`, a gap
in that catalog rather than a mistake here, verified 2026-09-16) ×
downstream outcomes for those tickers.

**What it buys**: turns "a human looked at it" from an assumption into
evidence. Does human override actually improve results, and on which
flag types specifically? This could tune which alerts are worth raising
at all — the exact same bounded-nudge, sample-gated pattern already used
for trade thresholds, applied instead to alert thresholds, closing the
loop on alert fatigue with real data instead of a fixed guess.

## G. Data-provenance intelligence — does forecast quality quietly depend on where the data came from

**Join**: `provider_fallback_log` (vinu-stock-price, built this session)
× `angle_calibration_entries` for the same symbol/window.

**What it buys**: does accuracy dip when a symbol's bars came from a
fallback provider instead of the primary? If so, the system's stated
confidence should already discount for that *before* it runs the angle
at all, not discover the effect after the fact by accident. This is a
join between a package (`vinu-stock-price`) that has no awareness
today of forecast outcomes, and a package (`vinu-research`) that has no
awareness today of data provenance — neither side currently knows the
other exists.

## H. Self-consistency / lineage intelligence

**Join**: `freeze_manifest`/`contamination_check` (currently a one-off,
manually-triggered research-vs-live comparison, `vinu_infra/freeze.py`
— real functions, verified 2026-09-16; absent from the 55-store catalog
because the manifest is an on-demand diagnostic snapshot with a
caller-supplied output path, not a store with a default persisted
location)
generalized into a *continuous* drift detector tracked longitudinally,
rather than spot-checked — plus `skill_edit_audit`'s content-hash change
history (currently orphaned, zero production readers) joined against
subsequent shifts in `trade_score_calibration_history`/
`calibration_entries`.

**What it buys**: is live behavior still consistent with what was
backtested, tracked continuously rather than only when someone
remembers to run the check? And: did editing the system's own risk
rules (`skill_edit_audit`) actually change downstream behavior, and for
better or worse? This turns two currently-inert audit trails into a real
answer to "did we actually improve when we changed something about
ourselves."

---

## Second pass: what A–H left untouched

A–H drew mostly from the calibration/decay/execution stores at the core
of the pipeline. A second look at the full 55-store catalog turns up a
whole layer still untapped: `vinu-screener`'s five stores (fully
decoupled from the main pipeline today — confirmed zero imports), the
agent's own process/cognition data (sessions, swarm debates, memory
retrieval), the mandate/governance layer, and the raw ingest pipeline
upstream of any forecast. None of these need new instrumentation either
— same rule as A–H: every signal already exists, just unjoined.

### I. Does the screener actually predict anything — an offline validation nobody's run

**Join**: `RankedSnapshotStore`'s `trace_json` + `RankerChurnStore`'s
entered/exited top-N events × the main pipeline's independent read on
the same tickers (`ticker_ledger`, `TickerSummaryStore`).

`vinu-screener` has been running the whole time, producing its own
independent signal, currently only consumed manually via Telegram
`/rank`. This join asks: when a symbol churned into a ranker's top-N,
did the main pipeline's Summary Agent/Planner *independently* flag it as
interesting around the same time? If yes consistently, that's real
evidence the screener is worth formally wiring in — validated with data
that already exists, before spending any integration effort.

### J. Screener churn rate as a regime-change leading indicator

**Join**: `RankerChurnStore`'s churn volume over time × `regime_tag`
transitions already labeled elsewhere in `vinu-research`.

A sudden spike in symbols entering/exiting rankers' top-N is plausibly a
leading signal that the market regime is shifting, before anything in
`vinu-research` gets around to relabeling `regime_tag`. If churn rate
reliably leads regime-tag changes, that's a free, already-computed
early-warning signal for the kind of regime transition the rest of the
system currently only detects after the fact.

### K. Does retrieved memory actually help, or is it decoration

**Join**: Unified memory store's `memory_entries`/`scored_search`
results + Facts registry (`facts`, disproven approaches) actually
injected into a given prompt × `team_runs`/`team_tasks`' verdict for
that run.

Both stores exist specifically to stop the system rediscovering
disproven approaches — but nothing today measures whether surfacing a
fact or memory entry actually changed the outcome. This join is a
direct A/B: runs where a relevant fact/memory was retrieved and
injected vs. runs where none was available, compared on verdict
quality. It's the difference between "we built a memory system" and "we
know our memory system works."

### L. Process-mining the agent's own reasoning traces

**Join**: the Session/Attempt store's `react_trace` and `metrics` per
attempt × the final artifact's realized outcome.

Every ReAct trace — tool sequence, retry count, how long reasoning ran
— is already saved per attempt. Joined against what that attempt's plan
eventually did in the market, this can surface real patterns: do longer
reasoning chains correlate with better or worse outcomes? Does a
specific tool-call sequence precede rejections? Genuine process mining
over the agent's own cognition, using data that's fully written and
currently just sitting in per-session JSON files.

### M. Does the investment-committee debate actually earn its cost

**Join**: Swarm runs (`find_latest_run`, debate final report) × realized
outcome for artifacts that did vs. didn't fold in a completed
`investment_committee` debate.

A near-natural-experiment already baked into the data — not every
artifact goes through a swarm debate before authoring. Comparing
outcomes for the ones that did vs. didn't answers whether the debate
pattern is actually improving decisions or just adding LLM cost and
latency for the same result.

### N. Could the kill-switch have fired earlier, using data the system already had

**Join**: the hash-chained safety ledger's halt/emergency-flatten
timestamps × `shock_clustering`/`shock_personality` angle readings and
realized volatility in the window immediately before each halt.

A retrospective "could we have seen this coming" audit: were the angles
the system already computes showing elevated shock signals before a
human or automated halt actually triggered? If so, that's a concrete
case for tightening the automatic trigger, backed by the system's own
historical near-misses rather than a guess.

### O. Are operator mandate limits protecting against real risk, or just friction

**Join**: `daily_limits`/`symbol_overrides`/`symbol_limits` +
`symbol_limit_history` × `trade_audit.log`'s `order_rejected` events ×
the eventual performance of the artifacts those limits blocked.

Every symbol that keeps hitting a cap or override has a paper trail of
*why* (`symbol_limit_history`'s `reason`/`set_by`) and a counterfactual
sitting right next to it: what would have happened if that trade had
gone through. This can show whether the mandate layer is catching real
risk or just capping strategies that would have been fine — evidence
for tuning the limits themselves, gated the same bounded-nudge way as
everything else.

### P. Does raw ingest health predict forecast quality, upstream of provider choice

**Join**: `symbol_catalog`'s `gap_count`/`has_adj_data`/`backfill_status`
+ `backfill_runs`' `rows_rolled`/errors + `ingest_log`'s per-attempt
`ok`/`error` history (added 2026-09-16 — a finer-grained signal than
`backfill_runs`' run-level rollup alone: catches a symbol with a string
of quietly-failing individual ingest attempts that never surfaces in the
aggregate) × `angle_calibration_entries` for the same symbol/window.

One layer earlier than G (which only looked at *which provider* served
the data) — this looks at whether the underlying data was ever gappy,
unadjusted, or partially rolled back in the first place, and whether
that predicts worse forecasts downstream. A genuinely leading indicator:
the system could know a symbol's forecasts deserve less trust *before*
running any angle at all, just from ingest bookkeeping that's already
collected.

### Q. Warm-starting — is it actually paying off, and is any weight lineage going stale

**Join**: `WeightsStore`'s `weights_ref` (used by 7 deep-learning
angles: arima, dlinear, itransformer, lpatchtst, lstm, patchtst, tft,
tips_regime_aware_transformer) × `angle_calibration_entries` for the
runs that used each weight lineage.

Two things in one join: does warm-starting from a prior walk-forward
step actually outperform cold starts (justifying the whole mechanism),
and separately, is any specific weight lineage being carried forward so
long without retraining that its angle's accuracy is quietly degrading
— an angle-specific staleness signal distinct from A's regime-based
decay.

### R. Is the Planner ever triaging against silently stale angle data

**Join**: `runs` (RunLog, vinu-initial-analysis)'s
`status`/`error`/`duration_seconds` × `ticker_summaries`'
`source_run_id`/`last_checked_run_id` × Planner triage timing.

A self-audit: does the Planner ever act on a `TickerSummaryStore` read
whose underlying angle run actually errored or went stale, without
anyone noticing? This checks whether the system's own freshness
guarantee (`ChangeGate`/`RunLogTrigger`) is actually airtight in
practice, using the exact audit trail already recorded for every run.

### S. Do the deterministic fact sheets and the LLM's own summary ever disagree

**Join**: Fact sheets (deterministic, no-LLM Markdown, regenerated every
batch but never read back) × the Summary Agent's LLM-written prose for
the same ticker/moment.

A free sanity check nobody runs today: the fact sheet is a ground-truth
deterministic rendering of the same angle data the LLM is summarizing
in prose. Comparing the two can catch the LLM inventing a number,
missing a real signal the deterministic sheet would have caught, or
just drifting from what the data actually says.

### T. The LESSON snapshots are already a crude proto-maturity signal — use them as a free baseline

**Join**: `vinu-live`'s LESSON JSON snapshots (closed-trade count,
win/loss streak, HALT state) × whatever `MaturityAssessor` eventually
computes.

Less "new analysis," more "free validation tool": the LESSON worker
already independently computes something maturity-shaped, crudely,
per-`vinu-live`-only. Once `MaturityAssessor` exists, checking it
against LESSON's independent numbers is a built-in sanity check that
costs nothing extra.

### U. Is the "critical" rebalance-request bypass actually justified

**Join**: `RebalanceRequestQueue`'s `critical` flag (bypasses the
5%-unrealized-gain protect rule) × the realized outcome of the position
that generated each request.

Are critical-flagged requests, which skip a real protective rule,
actually vindicated by what happens next — or is the flag being
overused as a way around the safety check? Directly measurable from
data already logged on both ends.

---

## Third pass (added 2026-09-16): four real gaps found by auditing A–U against the actual 55-store catalog

A–U's own closing claim — "nearly every one of the 55 cataloged stores
now has at least one concrete, joinable use" — was checked directly
against `project-understanding/05-full-recorded-information/README.md`
rather than taken on faith. Most of it holds (~48 of 55 genuinely
joined), but four stores turned up completely unused with no analysis
covering them, and one existing analysis (P) was thinner than the data
available to it. Each of the four gaps below slots into an *existing*
cluster in `agents-implementation-plan.md` (same folder) — none of them
justify a 7th analyst.

### V. Does paper performance actually predict live performance

**Join**: `paper_performance` (store #8, vinu-agent — per-artifact daily
paper-trading returns, `record_daily_return`/`get_daily_returns`) ×
the same artifact's realized live returns post-promotion
(`trade_score_calibration_history`/`calibration_entries`).

**What it buys**: this is the exact data needed to check whether
Shadow's `min_paper_days` promotion gate is actually calibrated — does
an artifact's paper-trading track record correlate with how it performs
once real capital is behind it, or is paper performance a weak/no
predictor of live performance? If the correlation is weak, that's
evidence the promotion bar itself needs rethinking, not just enforcing
harder. Completely unused across the original 21 despite being
purpose-built for exactly this question. Owner: **Regime & Risk
Coverage** (cluster 2, per `agents-implementation-plan.md`).

### W. Were the system's own hand-picked (never-measured) thresholds ever right

**Join**: `calibration_log.jsonl` (store #30, vinu-infra — reasoning-picked,
not measured, threshold decisions: rebalance-protect gain threshold,
bracket take-fraction, thesis-duplicate similarity cutoff) × the
realized outcome of whatever those thresholds gated.

**What it buys**: every other threshold in this system (TradeScore,
regime tilts, mandate limits) has some calibration mechanism checking it
against reality. This store exists specifically to record the handful
that don't — it's explicitly documented as "offline-only by design,"
meaning nobody has ever closed the loop on whether these particular
hand-picked numbers were ever actually right. Owner: **Governance &
Freshness** (cluster 5).

### X. Does the screener's *other* engine (condition-rule alerts) predict anything either

**Join**: `WatchAuditStore`'s `fired_watches` (store #38 — permanent
record of every condition-rule alert firing) × the main pipeline's
independent read on the same tickers around the same time (same shape
as I, but for the alert-rule half of `vinu-screener` instead of the
ranker half).

**What it buys**: `vinu-screener` actually ships two independent
engines — the factor ranker (validated by I and J above) and a separate
condition-based `ScanMonitor` alert-rule engine, which has zero
validation coverage in the original pass. Same question I already asks
for the ranker, asked of the half that was missed: when a condition rule
fires, does the main pipeline independently agree it mattered? Owner:
**External-Signal Cross-Check** (cluster 6) — a direct sibling of I,
not a new category.

### Y. Do trades held through an earnings/macro event lose more

**Join**: `events`/`events_meta` (store #49, vinu-stock-price — the
earnings/macro calendar `GET .../events/{symbol}` already serves) ×
`trade_audit_log.jsonl`'s per-trade entry/exit timestamps and realized
P&L (store #29).

**What it buys**: a classic, high-value, obvious question that was
simply absent from the original 21 despite both sides of the join
already existing and already being live-served — does a position held
through a known upcoming earnings/macro release lose more on average
than one that wasn't? If yes, that's direct evidence for tightening the
entry guard around event windows; if no, that's equally useful evidence
the current guard is already sufficient. Owner: **Execution &
Money-Flow** (cluster 3).

---

## The unifying point

Every one of these twenty-five is a **join across packages that doesn't
happen today**, not a new instrument, not new telemetry. That's the
difference between "adequate" and genuinely rich: this isn't inventing
measurement, it's finally letting measurement that already exists talk
to itself across the vinu-agent / vinu-research / vinu-portfolio /
vinu-live / vinu-screener / vinu-stock-price / vinu-initial-analysis /
vinu-infra boundary, where today each package only ever reads its own
tables. A–H drew from the core calibration/decay/execution stores; I–U
extend the same rule into the screener's isolated signal, the agent's
own process/cognition data, the mandate/governance layer, and the raw
ingest pipeline upstream of any forecast; V–Y (third pass) close four
gaps found by auditing that claim directly against the real catalog
rather than assuming it — between all three passes, every store in the
55-item catalog with genuine time-series/outcome content now has at
least one concrete, joinable use (the handful left out — `vinu_settings`,
`ParquetStore`, `angle_run_status`, dead/superseded code, and stores with
no production data yet, like the effectively-unwired Shadow account
profiles — have no real content to join in the first place, not an
oversight).

Together, these become the actual *content* of the Opinion/Observation
layer described in the reflective-loop thinking that followed
`maturity-agentic-system-explanation.md` — not one maturity tier, but a
queryable, structured, continuously-consolidating picture of exactly
what the system has earned the right to believe, sliceable by angle, by
regime, by strategy family, by ticker, by decision process, or by the
system's own governance and infrastructure choices.

## Where this could go next

Not committed to any build order here — this doc is deliberately just
the "what's possible" survey. From the first pass, two candidates stood
out as highest-leverage with zero new instrumentation required:

- **B (regime × strategy coverage map)** — because it's the most direct,
  actionable upgrade over a single maturity scalar: it tells a consumer
  agent exactly *where* to be cautious, not just *how much*.
- **D (decision-process intelligence)** — because `llm_calls.db` and
  `telemetry.db` are both fully-built, fully-written, zero-reader stores
  today; this is a pure join with no new writer needed at all.

From the second pass, two more stand out the same way:

- **I (screener validation)** — the lowest-risk way to decide whether
  `vinu-screener` is worth formally integrating, using data both sides
  already produce independently, before committing any wiring effort.
- **S (fact-sheet vs. LLM-summary divergence)** — the cheapest possible
  check to add, since both sides of the comparison already regenerate on
  every batch; it costs nothing but a diff.

From the third pass, one more stands out the same way:

- **Y (earnings/macro-event vs. loss)** — both sides of the join
  (`events`, `trade_audit_log.jsonl`) already exist and are already
  live-served; like S, this costs nothing but a diff, and answers a
  question anyone would ask first about a live trading system.

All seven (and every analysis above) would need the exact schema/query-
level scoping that `maturity-agentic-system-explanation.md` §3 did for
`MaturityAssessor` before being buildable — this doc stops short of that
on purpose, to keep the "what's possible" survey separate from "what we
commit to building first."
