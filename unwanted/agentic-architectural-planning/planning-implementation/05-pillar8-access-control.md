---
name: pillar8-access-control
status: confirmed-by-real-system
purpose: concrete answer to pillar 8 (who's allowed to touch what) from ../archi-think-1.md -- the enforcement mechanism this needs already exists and is already proven (ToolRegistry.subset()); the real work is a per-store, per-role access matrix and a naming discipline for the new tools, not new infrastructure.
---

> **This one held up and got built exactly this way.** The prediction
> below — that artifact-writing should never be an agent-callable tool,
> only manager-level Python called after a specialist's final answer —
> is exactly the pattern
> [../../../implementation/14-research-team-artifact-writing.md](../../../implementation/14-research-team-artifact-writing.md)
> used: `research_artifact_writer.py` is called directly from
> `TeamManager.run()`, never exposed as a tool any specialist can invoke.
> The specific table below (`create_version`, `mark_lab_approved`, ...)
> names methods that don't exist — see pillar 1's sync note for the real
> method names — but the *shape* (no LLM ever gets a raw write
> capability to this data) is confirmed correct, not superseded.
>
> **A second real team now confirms it's a pattern, not a one-off.**
> `risk_gatekeeper`'s manager never calls `mark_active()` itself — it
> only produces a `VERDICT: APPROVED/REJECTED` + JSON block; a
> manager-level hook (`agent/risk_gatekeeper_hook.py`, dispatched from
> `TeamManager.run()`'s generalized `_apply_team_result_hook()`) parses
> that and calls the real transition. Same shape as `research`'s hook,
> confirming this is the actual convention for every future team, not
> something specific to `research`.

# Pillar 8 — who's allowed to touch what

Reference: [../archi-think-1.md](../archi-think-1.md) (the 9 pillars),
[../../../01-orchestrator-and-teams-architecture.md](../../../01-orchestrator-and-teams-architecture.md)
(where this was first flagged as "a convention, not yet an enforced
filtered registry" and deliberately deferred).

## The good news: the enforcement mechanism already exists

This isn't a new problem needing new infrastructure. `build_registry()`
already scopes each specialist to only the tools its own `AGENT.md`
declares, via `ToolRegistry.subset(names)` — and this is **real
enforcement, not a convention**: an LLM's tool-calling can only ever
invoke a function that was included in the list passed to the API call.
If a tool isn't in a specialist's scoped registry, the model has no way
to call it — not "shouldn't," genuinely *can't*. This is why the original
architecture doc's deferred concern ("a risk-critic or idea-generator
specialist should never reach `trade_tool`") was really a **tool-design**
gap, not a missing enforcement layer: as long as every sensitive
capability is its own narrow tool, declared in exactly the right
`AGENT.md` files, the existing mechanism already locks everything else
out.

So pillar 8's actual job is: for every new tool pillars 1–7 and 9
introduced, decide exactly which role's `AGENT.md` gets to declare it —
and make sure no store-mutating capability is ever exposed as one broad
tool shared by multiple roles when a narrow, single-purpose one would do
(the same discipline pillar 6 already established for `strategy_specs`'
`advance_status`, just extended to the tool-registration layer).

## The access matrix

**Correction while writing this table:** an earlier draft listed
`create_version`, every `mark_*` transition, and `record_lesson` as
agent-callable tools declared in specific `AGENT.md` files. Checking that
against the actual specialist prompts already drafted in
[../../agents-explanation-in-detail/](../../agents-explanation-in-detail/)
— `strategy_writer`, `enhancer`, `trade_narrator` — none of them ever
call a create/mark/record tool. Each one just returns structured text as
its final answer. The real precedent for how that becomes a durable row
is already sitting in this codebase: `team_runs`/`llm_calls` are written
by infrastructure (`TeamManager`, `LoggingChatLLM`), never by an
agent-invoked tool. The new stores should follow the exact same shape —
which is a *stronger* answer than "scope the tool correctly," because
these write paths are never reachable by any LLM at all, not merely
scoped away from the wrong ones.

| Store | Write path | Who calls it | Read tool | Declared in |
|---|---|---|---|---|
| `strategy_specs` (create) | `StrategySpecStore.create_version()` | **not a tool** — `strategist`'s / `strategy_lab`'s `TeamManager.run()`, after parsing `strategy_writer`'s / `enhancer`'s final-answer JSON | `get_strategy_spec` | any role that needs it (low risk) |
| `strategy_specs` (status) | `mark_lab_approved` / `mark_lab_rejected` | **not a tool** — `strategy_lab`'s `TeamManager.run()`, after its own loop concludes | — | — |
| | `mark_gate_approved` / `mark_gate_rejected` | **not a tool** — `risk_gatekeeper`'s `TeamManager.run()`, after `exposure_reviewer`'s verdict | — | — |
| | `mark_funded` / `mark_not_funded` | **not a tool** — `capital_allocator`'s `TeamManager.run()` | — | — |
| | `mark_live` / `mark_closed` | **not vinu-agent at all** — see external-trigger note below | — | — |
| `memory_ledger` | `record_lesson` | **not a tool** — `post_trade_review`'s `TeamManager.run()`, after `trade_narrator`'s final answer | `search_strategy_ledger` | `strategist.strategy_writer`, `strategy_lab.enhancer` |
| `shadow_ledger_snapshots` | `record_tick` | **no team at all** — see note below | `get_position_comparison` (latest tick) | `trade_monitor.position_reviewer` |
| | | | `get_shadow_ledger_history` (full path) | `post_trade_review.trade_narrator` |
| `team_runs`/`team_tasks` | — | internal `TeamManager` plumbing only, never a tool | `list_by_spec_id` | the manager-verification check (§4.1) reads it directly, infrastructure-level, same as the writes above; whether `capital_allocator`'s manager gathers this itself or hands it to `allocation_analyst` as a real tool is undecided, consistent with that team's own provisional status |
| `llm_calls` | — | internal `LoggingChatLLM` wrapper only, never a tool | — | not exposed to any team currently |

Every write path in this table is reachable only from manager-level
Python code, never from an LLM's tool-calling surface — the specialist's
job ends at producing a structured final answer; turning that into a
durable, state-machine-checked row is the manager's own responsibility,
same division of labor `TeamManager` already has today for `team_runs`.

## Two genuinely different, non-agent access boundaries

- **`mark_live` / `mark_closed` aren't agent tools at all.** These
  transitions are triggered by Phase 6 execution and the real
  position-close event — both **outside vinu-agent entirely**. Whatever
  credential that external system uses to write these is a
  service-to-service auth question (ops/infra), not a `ToolRegistry`
  question. Worth being explicit that pillar 8 only governs
  agent-to-tool access; the vinu-agent/external boundary is pillar 4's
  territory, not this one's.
- **`shadow_ledger_snapshots`' write side has no agent access at all, on
  purpose.** Per pillars 5/6, this store is deterministic, LLM-free
  bookkeeping — no specialist should ever be able to write a tick, only
  read the result. There's no `AGENT.md` this write capability could
  correctly belong to; it's plain infrastructure code, not a tool.

## What this means for building it

Two enforcement layers, not one, and both already have real precedent:

- **For the genuine agent tools** (the read tools in the table, plus the
  external-data tools from pillar 4) — `ToolRegistry.subset()` already
  works. Discipline needed: each one is its own narrow function,
  registered under its own name, declared in exactly the `AGENT.md`
  files listed above — never a shared "generic store access" tool that
  would let the mechanism's guarantee quietly stop meaning anything.
- **For every write path that mutates a state machine** (everything
  marked "not a tool" above) — the enforcement is even simpler: the
  capability is never given to any `AgentLoop` at all, only to the
  manager-level Python that runs after one returns. There's no
  `ToolRegistry` question to get right here, because there's no tool.
