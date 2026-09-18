# Cluster 6 — External-Signal Cross-Check: I, J, T, X

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

---

## I. Does the screener's ranker actually predict anything

**Source stores**: `RankedSnapshotStore` (`vinu_screener/rankers/snapshot_store.py`:
`ranker_id, generated_at, top_json, trace_json`) + `RankerChurnStore`
(`vinu_screener/rankers/churn.py`: `ranker_id, symbol, kind
('entered'|'exited'), at, from_rank, to_rank`) × the main pipeline's
independent read on the same symbols around the same time
(`ticker_ledger`, `TickerSummaryStore`).

**Fetch**: per `ranker_id`, for each churn event (a symbol entering a
ranker's top-N), check whether the main pipeline (Summary Agent /
Planner) independently flagged that symbol as interesting within a
trailing window of the same event.

**Condition**: the agreement rate (main pipeline independently
interested within window) for this ranker crosses its own trailing
band, at `evidence_count ≥` a minimum sample of churn events.

**Storage**: `scope_type=system`, `scope_key=ranker_id`. `signal_json`:
`{agreement_rate, n_churn_events}`. `evidence_count` = # churn events
for this ranker to date.

**Manageability**: bounded by the number of active rankers
(`RankerStore`, small) — not per-ticker, even though the underlying
churn events are per-symbol, because the actionable question is "is
this ranker worth trusting," not "was this specific symbol correctly
called."

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/screener_agreement.py`
(implements I and X together — same shape, one module). The real
"main pipeline independently flagged this symbol" signal: the Planner
triage hook writes a `candidate_proposed` event
(`CANDIDATE_PROPOSED_EVENT_TYPE`, `vinu_agent/agent/thesis_intake_gate.py`)
into `ticker_ledger` — real, checkable, per-symbol, per-timestamp, not
invented for this. "Within a trailing window" implemented as a
symmetric ±48h window (the design doc doesn't specify a direction).
New `vinu-screener` dependency + `./data/screener` mount added to
`vinu-reflection`.

---

## J. Screener churn rate as a regime-change leading indicator

**Source stores**: `RankerChurnStore`'s churn volume over time ×
`regime_tag` transitions on `artifacts` (vinu-research).

**Fetch**: per `ranker_id`, compare churn-volume spikes to the timing
of subsequent `regime_tag` relabeling events.

**Condition**: churn volume crosses this ranker's own trailing P90 in
the window preceding a regime transition, at `evidence_count ≥` a
minimum sample of transitions observed.

**Storage**: `scope_type=system`, `scope_key=ranker_id`. `signal_json`:
`{churn_spike_lead_time, n_transitions_observed}`. `evidence_count` = #
regime transitions analyzed.

**Manageability**: bounded, small — system-wide by nature, never
per-ticker.

**Blocked, 2026-09-19 — not implementable as scoped.** Checked where
`regime_tag` actually gets written (`Artifact.regime_tag`): exactly one
assignment site in the whole codebase
(`vinu-agent/vinu_agent/agent/research_artifact_writer.py:159`), set
once at artifact-creation time and never updated afterward. There is no
"regime relabeling event" anywhere — `regime_tag` is a static per-artifact
attribute, not a continuously-tracked system state that transitions over
time. J's entire premise ("compare churn-volume spikes to the timing of
subsequent `regime_tag` relabeling events") assumes an event stream that
doesn't exist in this codebase. Would need a new writer that actually
tracks system-wide regime transitions as events, not a read of existing
data.

**Reframed and built, 2026-09-20.** `regime_tag`'s dead end wasn't the
whole story: `vinu-research/vinu_research/market_regime_analogue.py`'s
`get_market_regime_stats_for_today()` already computes a real, genuine
system-wide market-regime signal once per calendar day — a KNN match of
"today's" whole-market pattern against historical regime windows, giving
`positive_ratio`/`avg_return`/`median_return`/`max_drawdown` across the
matches, feeding `TradeScore.regime_fit_score`. It just had nowhere
durable to land: the result lived only in an in-memory, process-lifetime
`_DAY_CACHE`, and `TradeScoreResult` (which carries it) is never
persisted to `SqliteStrategyStore`. Closed by adding
`MarketRegimeHistoryStore` (`vinu-research/vinu_research/storage/
market_regime_history.py`, new): one row per calendar date
(`positive_ratio, avg_return, median_return, max_drawdown, n_matches,
n_positive, n_negative`), written the first time each day's stats are
computed — `get_market_regime_stats_for_today()` takes an optional
`history_store` param now, wired from `trade_plan_authoring.py`'s Phase 4
call site via a new `get_market_regime_history_store()` helper in
`vinu-agent/vinu_agent/broker/research_link.py` (same
`VINU_RESEARCH_DATA_ROOT`-direct pattern B/V/O already established).
`vinu_reflection/reflection/regime_drift.py` (new file) is J itself:
reads the history's full run, applies the same adjacent-window PSI trend
as `triage_freshness.py`/`angle_trust.py` on `positive_ratio`
(`CURRENT_WINDOW=10`, `REFERENCE_WINDOW_MAX=30`, `MIN_REFERENCE_WINDOW=10`
— smaller than R's 20/60 since this fires at most once per calendar day,
not per triage cycle), `scope_type=system`, `scope_key="market_regime"`.
Two real caveats, not implementation gaps: `regime_analogue_enabled` is
off by default (`config.py`), and persistence only happens on a day some
`author_trade_plan()` call actually runs the Phase 4 branch — sparser
than a guaranteed daily heartbeat, so this accumulates evidence more
slowly than the other 19 built analyses. Registered in `cli.py`'s
`ANALYSTS` now regardless, per the same "safe to ship ahead of data"
reasoning as U/Y/O/R.

---

## T. The LESSON snapshots as a free maturity-signal baseline check

**Source stores**: `vinu-live`'s LESSON JSON snapshots
(`vinu_live/lesson_worker.py::write_lesson()`:
`<data_root>/lessons/LESSON_<timestamp>.json` — `closed, fills,
avg_commission, last5, halted, at`) × `MaturityAssessor`'s own computed
tier (once built, per `../../maturity-agentic-system-explanation.md`).

**Fetch**: compare LESSON's crude, independently-computed
maturity-shaped read against `MaturityAssessor`'s tier at the same
point in time.

**Condition**: the two disagree in direction (e.g. LESSON implies
improving while `MaturityAssessor` implies degrading) — a direct
agreement/disagreement check, not a statistical band, since both sides
are already summary judgments rather than raw metrics.

**Storage**: `scope_type=system`, `scope_key="lesson_baseline_check"`.
`signal_json`: `{lesson_reading, maturity_tier, agree}`.
`evidence_count` = # comparison points made to date.

**Manageability**: bounded, effectively a single row, and only
meaningful once `MaturityAssessor` exists — low cadence by nature.

**Structurally blocked, confirmed 2026-09-19** — not a data gap, the
doc's own text already says why: `MaturityAssessor` doesn't exist yet.
Nothing to check until it's built.

---

## X. Does the screener's condition-rule alert engine predict anything either

**Source stores**: `WatchAuditStore`'s `fired_watches`
(`vinu_screener/audit/watch_history.py`: `id, rule_id, symbol,
fired_at, detail`) × the main pipeline's independent read on the same
symbols around the same time — the same shape as I, applied to
`vinu-screener`'s separate condition-based `ScanMonitor` alert-rule
engine rather than the factor ranker.

**Fetch**: per `rule_id`, for each fire event, check whether the main
pipeline independently flagged that symbol within a trailing window.

**Condition**: same shape as I — the agreement rate for this rule
crosses its own trailing band, at `evidence_count ≥` a minimum sample
of fire events.

**Storage**: `scope_type=system`, `scope_key=rule_id`. `signal_json`:
`{agreement_rate, n_fire_events}`. `evidence_count` = # fire events for
this rule to date.

**Manageability**: bounded by the number of active rules (`RuleStore`,
small) — a direct sibling of I, not a new category.

**Built 2026-09-19**: same module as I, `screener_agreement.py` (see
I's own entry above for the shared implementation detail) — reads
`WatchAuditStore.history()` (genuinely append-only, confirmed via
`vinu-screener/vinu_screener/audit/watch_history.py`'s own docstring:
"a fire is written here once and never mutated or reset").
