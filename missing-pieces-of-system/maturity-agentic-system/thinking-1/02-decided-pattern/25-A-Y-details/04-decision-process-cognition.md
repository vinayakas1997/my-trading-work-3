# Cluster 4 — Decision-Process / Cognition: D, L, K, M

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

**Build this cluster first** — per `../../agents-implementation-plan.md`'s
build order, **D** specifically is the recommended starting point: both
its source stores are fully-built, fully-written, zero-reader today, so
this is a pure read + join with no new writer needed anywhere.

---

## D. LLM call-quality vs. outcomes

**Source stores**: `llm_calls` (vinu-agent, `vinu_agent/storage/llm_calls.py`:
`call_id, tier, team, agent, role, retry_count, latency_sec, success,
token_count_source`) × `telemetry.db`'s `llm_calls`/`steps`
(vinu-infra) × downstream `risk_gatekeeper` verdicts (via
`team_runs.verdict`) and eventual trade outcomes (`trade_audit_log.jsonl`
joined via `team_runs.related_artifact_id`).

**Fetch**: per `llm_role` (the real role names in `roles.json` —
`orchestrator`, `forecast_skill`, etc.), compare downstream
verdict/outcome quality for calls with `retry_count > 0` vs.
`retry_count = 0`, and for `latency_sec` above vs. below this role's own
trailing median.

**Condition**: the rejection-rate delta (retry vs. no-retry) for this
role moves outside its own trailing self-calibrated band, at
`evidence_count ≥` a minimum sample (e.g. 30 calls) to avoid reacting to
noise from a handful of calls.

**Storage**: `scope_type=system`, `scope_key=llm_role`. `signal_json`:
`{retry_rejection_delta, latency_rejection_correlation}`.
`evidence_count` = # `llm_calls` rows for this role in the window.

**Manageability**: bounded by the fixed role list in `roles.json` —
small, never scales with watchlist size.

---

## L. Process-mining the agent's own reasoning traces

**Source stores**: the Session/Attempt store's `attempt.json`
(`react_trace`, `metrics`) × the attempt's linked artifact's eventual
outcome (via `team_runs.related_artifact_id` → `trade_audit_log.jsonl`
/ `calibration_entries`).

**Fetch**: per `team_name` (Planner, Researcher/Executor,
risk_gatekeeper), correlate `react_trace` length and tool-call sequence
against downstream outcome quality.

**Condition**: mean outcome quality for attempts with `react_trace`
length above this team's own trailing P75 diverges from attempts below
P25 by more than a self-calibrated band.

**Storage**: `scope_type=system`, `scope_key=team_name`. `signal_json`:
`{trace_length_outcome_correlation, flagged_tool_sequences}`.
`evidence_count` = # attempts analyzed for this team.

**Manageability**: bounded by the number of teams — small, fixed.

---

## K. Does retrieved memory actually help

**Source stores**: `memory_entries` (unified memory store) + `facts`
(registry, `kind` proven/disproven/known-bug) — specifically which
entries were actually injected into a given prompt (per session
metadata) × `team_runs.verdict` for that `session_id`.

**Fetch**: compare verdict quality for runs where a relevant
fact/memory was retrieved and injected vs. runs where none was
available.

**Condition**: the verdict-quality delta between "had relevant memory"
and "didn't" crosses its own trailing band, at `evidence_count ≥` a
minimum comparable-run sample.

**Storage**: `scope_type=system`, `scope_key=source`
(`facts_registry` | `unified_memory`). `signal_json`:
`{verdict_quality_with, verdict_quality_without}`. `evidence_count` = #
runs compared.

**Manageability**: bounded, tiny — only 2 `scope_key` values.

---

## M. Does the investment-committee debate earn its cost

**Source stores**: Swarm runs (`vinu_agent/swarm/store.py`:
`<base_dir>/<run_id>.json`, `status`, final report) × the realized
outcome of the linked artifact (via `trade_plan_data`/`origin_angles`
referencing the swarm `run_id`, folded in by `trade_plan_authoring.py`).

**Fetch**: compare outcome quality for artifacts that did vs. didn't
fold in a completed `investment_committee` debate before authoring.

**Condition**: the with-debate vs. without-debate outcome delta crosses
its own trailing band, at `evidence_count ≥` a minimum sample (e.g. 10
debated artifacts).

**Storage**: `scope_type=system`, `scope_key="investment_committee"`.
`signal_json`: `{with_debate_outcome, without_debate_outcome,
n_debated}`. `evidence_count` = # debated artifacts to date.

**Manageability**: bounded, effectively a single row.
