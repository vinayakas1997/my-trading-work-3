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

**Blocked, 2026-09-19 — not implementable as scoped, needs a new
writer.** Checked against the real prompt-injection path
(`vinu-agent/vinu_agent/agent/context.py`, the block that calls
`facts_registry.active_facts_for(...)` / `unified_memory.list_by_symbol(...)`):
the results are formatted straight into the prompt's free-text
`user_message` — **no structured record of which specific
`memory_entries.id` / `facts.id` were actually selected is written
anywhere** (not on `Attempt`, not on `Session.config`, no sidecar
table). The only trace is the full prompt text itself, which would need
lossy text-matching against `memory_entries.title`/`facts.statement` to
reconstruct — not a real queryable link, and not what "per session
metadata" in this analysis's own Fetch description implies exists.
Two ways forward, neither attempted yet: (a) add a real writer — record
selected memory/fact IDs onto the session or a new sidecar table at
injection time in `context.py` (turns K into a normal read+join
afterward, same shape as every other analysis here), or (b) rescope K
to the lossy text-match approximation and accept it's not a real FK-style
join. Left undecided — this is a real product/priority call (is K worth
a new writer), not a design detail to just pick silently.

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
