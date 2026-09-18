# Cluster 4 — Decision-Process / Cognition: D, L, K, M

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

**Build this cluster first** — per `personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`'s
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

**Built 2026-09-18**: `vinu-reflection/vinu_reflection/reflection/decision_process.py`.
`latency_rejection_correlation` was not implemented (only
`retry_rejection_delta`) — scoped down during implementation, see that
module's own history for why. `telemetry.db` was not joined either;
`llm_calls`/`team_runs` alone were sufficient for the real Condition
being checked.

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

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/process_mining.py`.
**Correction found while implementing**: `Attempt` (the Session/Attempt
store's real dataclass) has no `team_name` field — the actual join to a
team is via `Attempt.session_id == TeamRun.triggered_by_session_id`
(same best-available-approximate-join posture already documented for D's
`TeamRunStore.get_latest_verdict_by_session_id`), not a direct FK. Outcome
quality is `calibration_entries.directional_correct`, meaned per artifact
— `trade_audit_log.jsonl` was not joined (calibration_entries alone gave
a clean, already-computed quality signal). `flagged_tool_sequences` (the
second half of the original `signal_json` shape) was not implemented —
scoped down to the trace-length half of the Condition only.

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

**Built 2026-09-20**, once the user explicitly decided K's new writer
was worth adding (the product/priority call this file left open
2026-09-19). Checked against the real prompt-injection path
(`vinu-agent/vinu_agent/agent/context.py`, the block that calls
`facts_registry.active_facts_for(...)` / `unified_memory.list_by_symbol(...)`)
and confirmed the original finding: the results were formatted straight
into the prompt's free-text `user_message` with no structured record of
which specific `memory_entries.id` / `facts.id` were actually selected.
Closed via option (a) from the two choices this file previously left
undecided: `ContextBuilder.build_messages()` now captures the real IDs
it already has in hand (`Fact.id`, `MemoryEntry.id`) into
`_last_injected_fact_ids`/`_last_injected_memory_ids` (exposed as
`last_injected_fact_ids`/`last_injected_memory_ids` properties, same
pattern as the pre-existing `last_facts_msg` etc.), including the
token-budget-trimmed case (only IDs whose line actually made it into
the trimmed block are recorded). `vinu_agent/storage/injected_context_log.py`
(new file, `InjectedContextLogStore`) is the new writer: one row per
`build_messages()` call, keyed by `session_id`, written from
`session/service.py` right after the call (best-effort — only writes a
row when something was actually injected, since "no row" already means
"nothing available" for K's join). No `docker-compose.yml` change
needed: the new `injected_context_log.db` lands in the same vinu-agent
data root already mounted read-only into `reflection-worker`.
`vinu_reflection/reflection/memory_effectiveness.py` (new file) is K
itself — same `TeamRunStore.get_latest_verdict_by_session_id` join key
analysis D already established, joined against "did this session ever
have a fact/memory injected" (a new pure-read `TeamRunStore.
distinct_session_ids_with_verdict()` supplies the session universe).
Two independent findings, one per `scope_key` (`facts_registry` /
`unified_memory`), each comparing verdict quality (1 - reject rate)
between sessions that had that source injected vs. sessions that
didn't. See that module's own docstring for the full reasoning.

---

## M. Does the investment-committee debate earn its cost

**Source stores**: Swarm runs (`vinu_agent/swarm/store.py`:
`<base_dir>/<run_id>.json`, `status`, final report) × the realized
outcome of the linked artifact (via `trade_plan_data`/`origin_angles`
referencing the swarm `run_id`, folded in by `trade_plan_authoring.py`).

**Correction, 2026-09-19**: the swarm `run_id` is never actually
persisted into `trade_plan_data`/`origin_angles` (`SignalEntry`, the
model that lands in `trade_plan_data.forecast.signals`, has no `run_id`
field; `origin_angles` is a distinct, unrelated field — initial-analysis
angle names, never swarm run ids). The real, available join needs no
swarm-store read at all: `trade_plan_authoring.py`'s `fetch_debate_signal`
(gated on `config.debate_signal_enabled`) appends one `SignalEntry` with
`source="investment_committee"` into `forecast.signals` before the plan
freezes into `Artifact.trade_plan_data` — presence/absence of that one
signal, per artifact, **is** "did vs. didn't fold in a debate," a real
ID-free join. `vinu_agent/swarm/store.py` is not read by the built
implementation below at all.

**Fetch**: compare outcome quality for artifacts that did vs. didn't
fold in a completed `investment_committee` debate before authoring.

**Condition**: the with-debate vs. without-debate outcome delta crosses
its own trailing band, at `evidence_count ≥` a minimum sample (e.g. 10
debated artifacts).

**Storage**: `scope_type=system`, `scope_key="investment_committee"`.
`signal_json`: `{with_debate_outcome, without_debate_outcome,
n_debated}`. `evidence_count` = # debated artifacts to date.

**Manageability**: bounded, effectively a single row.

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/debate_value.py`,
using the corrected join above.
