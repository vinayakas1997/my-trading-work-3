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

**Built 2026-09-20**, once the user explicitly decided O's join key was
worth adding, then also the analyst itself once asked "can't we just
build it so it's ready when it starts working." Checked directly
(`vinu-agent/vinu_agent/broker/order_guard.py`) and confirmed the
earlier finding: the operator-limit rejection sites
(`_check_symbol_override`'s hard block, and the
`max_order_value`/`max_position_pct`/`max_capital_utilization_pct`
checks via `_effective_limit`) never looked up which artifact they were
blocking — pure numeric/override checks with no artifact lookup at all.
Closed by adding a new `GuardResult.blocked_artifact_ids: list[str]`
field, populated at exactly those four rejection sites via a new
`OrderGuard._blocked_artifact_ids(symbol)` helper (the same
`list_artifacts_for_symbol` call `_check_active_artifact` already makes,
broadened to `[ACTIVE, BENCHING, MONITORING]` — O's own "trackable"
statuses). `trade_tool.py`'s two real `order_rejected` audit-log call
sites (the `guard.check()` rejection and `guard.pre_approve()`'s
re-check) now include it. Every other rejection reason (kill switch,
mandate expiry, allowlist, short-selling, daily limits, market-closed,
no-active-artifact, portfolio concentration) is deliberately left with
an empty list — none of those are the "operator mandate limits" O is
asking about.

`vinu_reflection/reflection/mandate_limit_friction.py` (new file) is O
itself. "Eventual projected performance... where trackable" is read from
`decay_snapshots` via `get_strategy_store().get_latest_snapshot
(artifact_id)` — same `get_strategy_store()` B/V already use (this
module does **not** take a `data_root_paths["vinu_research"]` key; that
key doesn't exist in `cli.py`'s real wiring, a bug caught in testing
before it shipped). A snapshot's mere existence for a blocked artifact
already means it's still being tracked; `evaluation == "HEALTHY"` (the
only "nothing wrong" value `vinu_research/decay.py` ever returns) is the
"good outcome" flag. `MIN_EVIDENCE_COUNT = 10` (rarer than raw order
flow, per this file's own Manageability note) gates both the system-wide
baseline and any per-symbol finding. Writes nothing until real
production rejections against real trackable artifacts accumulate --
registered in `cli.py`'s `ANALYSTS` now. See that module's own docstring
for the full reasoning.

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

**Built 2026-09-20**, same "writer, then the analyst too" pass as O.
Re-confirmed the original finding: `ticker_summaries`
(`vinu-agent/vinu_agent/storage/ticker_summaries.py`) is deliberately
non-versioned ("overwritten (not versioned) on each new screener run"),
so there is genuinely no way to reconstruct what it said at an arbitrary
*past* Planner-triage timestamp -- reversing that design decision was
never on the table. Closed instead via the scoped-down version this file
previously described but left unbuilt: found the real "Planner triage
event" call site (`ChangeGate`'s `run_gate_cycle` → `_on_yes` in
`vinu_agent/agent/scheduler_workers.py`, wired from `planner-worker` in
`cli.py`) and added a LIVE check right there — at the moment each triage
event fires, `_log_triage_freshness()` calls the same `RunLogReader.
latest_run_id(ticker)` `RunLogTrigger` already uses elsewhere, compares
it against `gate_result.run_id_seen` (the run this triage actually acted
on), and logs one of three exact event_types (`triage_freshness_fresh`/
`_stale`/`_unknown` -- deliberately not free text, so nothing downstream
ever has to substring-match a human-readable string) to the existing
`TickerLedgerStore`. This answers a real but narrower question than the
original ("was this specific triage looking at stale data, checked live,
going forward") rather than the original's unanswerable "was the Planner
*ever* triaging against stale data" over arbitrary past history — an
explicit, documented scope-down, not a silent substitution.

`vinu_reflection/reflection/triage_freshness.py` (new file) is R itself.
Two new pure-read methods on `TickerLedgerStore`
(`list_events_by_type`/`list_events_by_types`) supply the event stream,
ordered by SQLite `rowid` rather than `timestamp` -- a real bug found
while testing this module: `timestamp` is only second-resolution, so
several events written within the same second (routine under a burst of
triage cycles, and the common case in any fast test) came back in an
unspecified order among themselves when sorted by it. Primary (system-
wide) follows `angle_trust.py`'s adjacent-window PSI precedent
(`CURRENT_WINDOW=20`/`REFERENCE_WINDOW_MAX=60`) rather than the design
doc's literal "trailing band" phrasing, same reasoning A gave. Secondary
(per-ticker repeat offenders, `stale_count >= 3`) is a flat threshold,
implemented literally with `domain_floor_breached=True` (no PSI needed
for a threshold crossing). `_unknown` events (a live lookup failure) are
excluded from the trend entirely. Writes nothing until real triage
cycles accumulate -- registered in `cli.py`'s `ANALYSTS` now. See that
module's own docstring for the full reasoning.

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

**Investigated and built, 2026-09-20.** Turned out to need the real
investigation, not a schema change: `significance_flags`
(`vinu_agent/agent/significance_triage.py`) already has `ticker`,
`created_at`, and `resolved` — exactly the columns this analysis needs.
"Downstream outcome for the flagged ticker" reuses the exact weak
symbol+time join U (`rebalance_bypass.py`) already established against
`trade_audit_log.jsonl`'s real exit rows: the first exit for that ticker
at or after the flag's `created_at`. The only real gap was
`SignificanceFlagStore` having no way to read every flag —
`get_flag(flag_id)` is a single lookup, `response_rate()` gives only
aggregate counts. Added `all_flags()` (ordered by SQLite `rowid`, not
`created_at`, after remembering `_now()` is second-resolution and
`run_significance_cycle` can create several flags back-to-back — the
same class of ordering bug found and fixed for R, applied proactively
here without needing to hit it first). `significance_response_outcome.py`
(new file) is F itself, `scope_type=system`/`scope_key=reason` (the flag
`reason` string doubles as `flag_type`), `MIN_EVIDENCE_PER_GROUP=5` (same
"rare events by design" order of magnitude as U). One real, permanent
caveat, not a bug: `llm_failure_rate` flags use a sentinel ticker
(`"SYSTEM"`) that never appears in `trade_audit_log.jsonl`, so that
`reason` never accumulates evidence here — correct, since "did a human
response change this position's outcome" has no real position to check
for a system-wide LLM-failure alert in the first place.

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

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/
threshold_calibration.py`. **Real scoping correction found while
implementing**: the "swept range of nearby values would plausibly have
produced" counterfactual has no existing helper anywhere in this
codebase to build against (same "needs a spec" situation as analysis S)
— implemented instead as the same two-adjacent-windows drift detector
every other analyst here uses, applied directly to each checkpoint's own
logged numeric field (answers "did this checkpoint's real behavior
drift from its own baseline," not "would a different value have done
better"). Also found: only 2 of the design doc's 3 named checkpoints
have a real writer — grepped every `calibration_log.record()` call site
in vinu-live and found `bracket_partial`/`rebalance_protect` real, but
no "thesis-duplicate similarity cutoff" checkpoint anywhere in real
code; not built, since it doesn't exist to build against. Also found and
fixed a real infra bug along the way: `live-api` had no
`VINU_CALIBRATION_LOG` set in `docker-compose.yml` — same "writes to the
container's ephemeral `$HOME`, not the mounted `/data` volume" bug
already found and fixed once for `trade_audit_log.jsonl`.

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
dropped from `signal_json`.

**Consistency piece built 2026-09-19**: `vinu-reflection/vinu_reflection/
reflection/consistency_freeze.py`. **Real correction to this file's own
framing**: `freeze_manifest`/`contamination_check` turned out to need no
refactor at all — they're already plain, argument-only functions with no
CLI/argparse dependency; grepping the whole tree found no caller
anywhere, meaning they were simply unused, not "manually-triggered" as
this file previously said. **Real scoping correction**: both functions
operate on global `VINU_*_DATA_ROOT` file hashes and `VINU_*` env vars,
never per-`strategy_family` — the design doc's `signal_json` sketch
(`{live_backtest_divergence, divergence_trend}`) assumed a
`strategy_family`-scoped join that doesn't exist here (the same gap
already documented for analysis B doesn't even apply — this piece never
needed to join to it). Implemented as a single `scope_type=system`
finding, `domain_floor_breached=True` on any real drift (added/removed/
changed file hash or changed env var) rather than a PSI comparison,
since `contamination_check()` returns a structural diff, not two
numeric distributions. Prior-cycle manifest persisted to this service's
own data root as `freeze_manifest_state.json`, not through
`reflection_beliefs` (routine cycles write nothing there at all).
