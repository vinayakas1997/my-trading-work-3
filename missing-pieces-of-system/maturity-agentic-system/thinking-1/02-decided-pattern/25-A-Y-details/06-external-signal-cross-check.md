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
