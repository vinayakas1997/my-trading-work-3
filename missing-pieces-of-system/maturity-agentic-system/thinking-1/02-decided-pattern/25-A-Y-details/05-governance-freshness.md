# Cluster 5 — Governance & Freshness: O, R, F, W, H

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

**Not attempted, 2026-09-19.** "Compare the blocked artifact's eventual
projected performance against the system's typical performance for
similar artifacts" needs real investigation before building: what
"eventual projected performance" of an artifact that never entered
BENCHING actually means, and what "similar artifacts" resolves to (the
same `strategy_family` gap already blocking B). Not checked this pass —
flagged rather than guessed at.

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

**Blocked, 2026-09-19 — same current-state-only limitation as K/P/G/Y/U.**
Checked `ticker_summaries` (`vinu-agent/vinu_agent/storage/ticker_summaries.py`)
directly: its own docstring says it outright -- "One row per ticker,
overwritten (not versioned) on each new screener run... `team_runs`
already keeps the full run history if that's ever needed." `runs`
(RunLog, vinu-initial-analysis) and `team_runs.created_at` are both real
history, confirmed, but `ticker_summaries` only ever shows its *current*
value -- there's no way to reconstruct what it said at an arbitrary past
Planner-triage timestamp, only whether the run it currently references
happens to be stale/errored *right now*. A scoped-down version ("is the
currently-referenced run currently stale, sampled against team_runs'
history of triage timestamps") is possible but answers a materially
different question than "was the Planner ever triaging against stale
data at the time" — left unbuilt rather than silently substituted.

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

**Not attempted, 2026-09-19.** "Downstream outcomes for the flagged
tickers" isn't a checked, concrete join yet — needs the same kind of
real investigation P/G/Y/U got before assuming it's buildable. Flagged,
not guessed at.

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

**Not attempted, 2026-09-19.** The design doc's own text flags the real
difficulty: "the join varies per checkpoint" — this needs a per-checkpoint
investigation pass (what a swept range of nearby values would plausibly
have produced isn't a simple read, it's a counterfactual), not a single
generic implementation. Flagged, not guessed at.

---

## H. Self-consistency / lineage intelligence — the previously unassigned analysis, closed out here

Real, verified (`vinu_infra/freeze.py`, `vinu_agent/agent/skill_audit.py`
— both confirmed real code), but had fallen out of every cluster
assignment until now. Belongs here because both its pieces answer the
same question this cluster already owns: is our own process — our
backtest-to-live pipeline, our own rule edits — actually trustworthy.
Both source stores are colocated in vinu-agent's container (same mount
confirmation `02-analyst-interface.md` already made for D): `skill_edit_audit`
is vinu-agent's own; `trade_score_calibration_history` is mounted from
vinu-research at `/research-data`. Zero new HTTP wiring needed.

**Source stores (consistency piece)**: `freeze_manifest`/
`contamination_check` (`vinu_infra/freeze.py` — currently a one-off,
manually-triggered research-vs-live comparison, generalized here into a
continuous check run on the worker's own schedule instead of only when
someone remembers to trigger it) × `trade_audit_log.jsonl`'s realized
outcomes for the same artifacts/window.

**Source stores (governance piece)**: `skill_edit_audit`
(`vinu_agent/agent/skill_audit.py` — content-hash change history to the
system's own risk rules, currently orphaned, zero production readers) ×
`trade_score_calibration_history` (`vinu_research/trade_score_calibration.py`)
for whatever artifact/strategy family the edited rule affects.

**Fetch (consistency)**: run freeze_manifest's existing research-vs-live
comparison on a schedule per `strategy_family`, rather than on-demand;
flag when live behavior diverges from what was backtested.

**Fetch (governance)**: for each `skill_edit_audit` entry, compare
`trade_score_calibration_history`'s realized-outcome distribution in the
trailing window *after* that edit against the same artifact/strategy's
own trailing window *before* it.

**Condition (consistency)**: the freeze-manifest divergence for this
`strategy_family` moves outside its own trailing band — same
self-calibrated PSI rule as every other analysis in this cluster.

**Condition (governance)**: **event-triggered, not cycle-gated** — same
shape as N (kill-switch retrospective). Runs only when a new
`skill_edit_audit` entry appears; flags when the after-edit
outcome-quality window diverges from the before-edit window by more
than a self-calibrated band. Not a recurring PSI trend — see
`04-reference-baseline-config.md`, which marks this piece `n/a` for the
same reason N is `n/a` there: a discrete before/after comparison per
edit, not a belief that trends over time.

**Storage (consistency)**: `scope_type=strategy_family`,
`scope_key=strategy_family`. `signal_json`: `{live_backtest_divergence,
divergence_trend}`. `evidence_count` = # windows compared for this
family.

**Storage (governance)**: `scope_type=system`,
`scope_key="skill_rule_edits"`. `signal_json`: `{edit_id,
outcome_delta_before_after, affected_strategy_family}`.
`evidence_count` = # skill edits analyzed to date.

**Manageability**: consistency piece bounded by strategy-family count
(small, fixed). Governance piece bounded by the real rate of skill
edits — deliberate, infrequent changes by design, negligible volume,
same category as N.

**Governance piece built 2026-09-19**: `vinu-reflection/vinu_reflection/
reflection/skill_edit_governance.py`. **Scoping correction found while
implementing**: `trade_score_calibration_history` rows carry no
artifact/strategy id at all, only `timestamp, direction,
actual_return_pct, tier, total_score` + sub-scores — there's no real way
to scope the before/after comparison to "whatever artifact/strategy
family the edited rule affects" as described; implemented as a
system-wide before/after comparison instead, `affected_strategy_family`
dropped from `signal_json`. Consistency piece not attempted — needs
`freeze_manifest`/`contamination_check` generalized from its current
one-off manually-triggered shape into something callable on a schedule,
a real refactor of `vinu_infra/freeze.py`, not just a new reader.
