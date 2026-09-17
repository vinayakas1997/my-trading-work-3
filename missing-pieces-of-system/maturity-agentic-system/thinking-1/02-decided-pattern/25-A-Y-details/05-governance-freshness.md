# Cluster 5 — Governance & Freshness: O, R, F, W

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

---

## O. Are operator mandate limits protecting against real risk, or just friction

**Source stores**: `symbol_limits`/`symbol_overrides`
(`vinu_agent/broker/symbol_limits.py`, `symbol_overrides.py`) +
`symbol_limit_history` (`symbol, field, old_value, new_value, reason,
set_by, changed_at`) × `trade_audit.log`'s `order_rejected` events ×
the eventual performance of the blocked artifact where trackable (via
`decay_snapshots`/`calibration_entries` if it exists in
BENCHING/MONITORING despite the block).

**Fetch**: per symbol with an active limit/override, compare the
blocked artifact's eventual projected performance against the system's
typical performance for similar artifacts.

**Condition**: blocked artifacts for this symbol show typical or
above-typical projected performance more often than this symbol's own
trailing comparison band would suggest — i.e. the limit looks like it's
blocking otherwise-fine trades — gated by a minimum sample of trackable
blocked artifacts.

**Storage**: `scope_type=ticker`, `scope_key=symbol` — only for symbols
with an active limit (a small subset of the watchlist). `signal_json`:
`{blocked_count, projected_performance_of_blocked}`. `evidence_count` =
# blocked artifacts trackable for this symbol.

**Manageability**: bounded to the subset of the watchlist that actually
has an active limit set — typically small in practice, not the full
watchlist.

---

## R. Is the Planner ever triaging against silently stale angle data

**Source stores**: `runs` (RunLog, `vinu_initial_analysis/storage/meta.py`:
`status, error, duration_seconds`) × `ticker_summaries`
(`source_run_id, last_checked_run_id`) × Planner triage timestamps
(`team_runs.created_at` for Planner runs).

**Fetch**: for each Planner triage event, check whether the
`TickerSummaryStore` read it acted on referenced an angle run that was
errored or stale at the time.

**Condition (primary, system)**: the fraction of triage cycles acting
on stale/errored data this week crosses this system's own trailing
band. **Condition (secondary, per-ticker)**: a specific symbol shows
this pattern repeatedly (≥3 occurrences).

**Storage (primary)**: `scope_type=system`,
`scope_key="triage_freshness"`. `signal_json`: `{stale_fraction,
n_incidents}`. `evidence_count` = # triage cycles audited.

**Storage (secondary)**: `scope_type=ticker`, `scope_key=symbol`, only
for repeat offenders.

**Manageability**: primary bounded to a single row; secondary rare.

---

## F. Human-in-the-loop as a measured variable

**Source stores**: `significance_flags` (`flag_id, ticker, reason,
resolved, response_text`, `response_rate()`) × `HypothesisRegistry`'s
human-sourced theories (`vinu_research/hypothesis_registry.py`) ×
downstream outcomes for the flagged tickers.

**Fetch**: per `flag_type` (repeated-rejection, large-funding,
thesis-contradiction, `llm_failure_rate` — the four known Significance
Triage detector types), compare outcomes for flags that got a human
response vs. those that were unresponded/muted.

**Condition**: the responded-vs-unresponded outcome delta for this
`flag_type` crosses its own trailing band, at `evidence_count ≥` a
minimum sample of flags of that type.

**Storage**: `scope_type=system`, `scope_key=flag_type`. `signal_json`:
`{response_rate, outcome_delta}`. `evidence_count` = # flags of this
type to date.

**Manageability**: bounded by the fixed 4 detector types — small,
never scales with watchlist size.

---

## W. Were the system's own hand-picked thresholds ever right

**Source stores**: `calibration_log.jsonl` (`vinu_infra/calibration_log.py`:
`{checkpoint, timestamp, ...context}` for `rebalance_protect`,
`bracket_partial`, the thesis-duplicate similarity cutoff — explicitly
"offline-only by design") × the realized outcome of whatever each
checkpoint gated (the join varies per checkpoint — e.g. `bracket_partial`
joins to `trade_audit_log.jsonl`'s `realized_pnl` for the position that
triggered it).

**Fetch**: per checkpoint name, pull every `calibration_log.jsonl` entry
and its downstream realized outcome.

**Condition**: the realized-outcome distribution for decisions gated by
this checkpoint's current hand-picked value diverges from what a swept
range of nearby values would plausibly have produced, by more than a
self-calibrated band, at `evidence_count ≥` a minimum sample.

**Storage**: `scope_type=system`, `scope_key=checkpoint_name`.
`signal_json`: `{current_value, outcome_under_current,
outcome_under_alt_range}`. `evidence_count` = # `calibration_log.jsonl`
entries for this checkpoint.

**Manageability**: bounded by the fixed checkpoint list (currently 3),
independent of watchlist size.
