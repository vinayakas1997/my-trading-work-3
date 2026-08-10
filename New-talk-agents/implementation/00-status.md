---
name: implementation-status
status: core-mechanism-done
purpose: running log of the orchestrator+teams build for vinu-agent — what's built, what's left, bugs found/fixed along the way, and any decisions made mid-implementation that weren't already pinned down in ../01-orchestrator-and-teams-architecture.md.
---

# Implementation status — orchestrator + teams

Design reference: [../01-orchestrator-and-teams-architecture.md](../01-orchestrator-and-teams-architecture.md).
This file tracks *building* it — update as work happens, don't let it go stale.

## How this folder works

- This file (`00-status.md`) is the index/status tracker — the table below
  is the single place to check what's done and what isn't.
- One file per component once there's real content to say about it (e.g.
  `01-team-manager.md`, `02-delegate-tool.md`) — bugs found, decisions made
  while building it, anything that deviated from the original design doc
  and why. Link them from the table below, don't duplicate content here.
- If something built differs from what `01-orchestrator-and-teams-architecture.md`
  said, note it here with the reason — that file is the *plan*, this one is
  the *as-built* record.

## Status table

| # | Component | File | Status | Notes |
|---|-----------|------|--------|-------|
| 1 | Wiring survey (session/service.py, config.py, server/app.py) | — | done | see "Deviations" — no new route/class needed for the orchestrator itself |
| 2 | Research team scaffold (TEAM.md, AGENT.md + prompt.md files) | [teams/research/](../../vinu-components/vinu-agent/teams/research/) | done | idea_generator, backtest_runner, risk_critic |
| 3 | `agent/team.py` — generic TeamManager | [agent/team.py](../../vinu-components/vinu-agent/vinu_agent/agent/team.py) | done | |
| 4 | `tools/delegate_tool.py` — delegate_to_team | [tools/delegate_tool.py](../../vinu-components/vinu-agent/vinu_agent/tools/delegate_tool.py) | done | `delegate_to_agent` lives in `agent/team.py` (manager-scoped, built per-team, not a top-level auto-discovered tool) |
| 5 | `team_runs` / `team_tasks` storage | [storage/team_runs.py](../../vinu-components/vinu-agent/vinu_agent/storage/team_runs.py) | done | `TeamRunStore(SQLiteBackend)`, exact schema from the design doc |
| 6 | SSE progress side-channel for team runs | [agent/team.py](../../vinu-components/vinu-agent/vinu_agent/agent/team.py)`::_tag_event_callback` | done | simpler than planned — see "Deviations" |
| 7 | Orchestrator entry point wiring | — | done | see "Deviations" — folded into #1 |
| 8 | Tests (team.py, delegate_tool.py, storage, discovery scoping, frontmatter) | `tests/test_team.py`, `tests/test_delegate_tool.py`, `tests/test_team_runs_storage.py`, + additions to `tests/test_tools.py`, `tests/test_tools_discovery.py`, `tests/test_skills.py` | done | 45 new tests |
| 9 | Full vinu-agent regression suite | — | done | 386/386 passing (see cumulative counts per addition below). No downstream package imports `vinu_agent`, confirmed via repo-wide grep, so no further downstream regression pass needed. |
| 10 | Retire `vinu-research`, remove superseded vinu-agent files | — | not-started | deliberately not done yet — this deletes a whole running service; wait for explicit go-ahead once the research team has been exercised for real, not just under test |
| 11 | Per-tier LLM config (orchestrator can use its own provider/model, independent of teams/specialists) | `config.py`, `agent/llm.py`, `service.py`, `session/service.py` | done | opt-in via `VINU_ORCHESTRATOR_LLM_*` env vars, documented in `.env-example`; unset means orchestrator transparently shares the existing `VINU_LLM_*` config. 363/363 at this point. |
| 12 | Every-LLM-call logging (full prompt, response, tokens, latency, tagged by tier/team/agent/role) | [storage/llm_calls.py](../../vinu-components/vinu-agent/vinu_agent/storage/llm_calls.py), `agent/llm.py::LoggingChatLLM`/`wrap_with_logging` | done | wraps the orchestrator's, every manager's, and every specialist's LLM client transparently — no call site has to remember to log itself. 386/386 at this point (23 new tests, including the first-ever real `AgentService()` construction test). |

## Bugs found and fixed during this build

### 1. `build_registry()`'s tool auto-discovery was accidentally global, not package-scoped

**What broke it:** `vinu_agent/tools/__init__.py`'s `_discover_subclasses()`
imports every module under `tools/`, then calls `BaseTool.__subclasses__()`
to collect tool classes. `BaseTool.__subclasses__()` is process-global in
Python — it returns *every* subclass that has ever been defined anywhere,
not just the ones in `tools/`. The moment `agent/team.py`'s
`DelegateToAgentTool` (a `BaseTool` subclass that's deliberately
constructed per-team with required arguments — `agents`, `full_registry`,
`llm` — not meant to be auto-registered) got imported by
`tools/delegate_tool.py`, it became "discoverable," and `build_registry()`
tried to zero-arg-construct it: `TypeError: DelegateToAgentTool.__init__()
missing 1 required positional argument: 'agents'`. Broke 9 existing tests
(`test_tools_discovery.py`, `test_agent_integration.py`).

**Why it mattered beyond this one crash:** this was a latent, pre-existing
fragility, not something new-code-specific — *any* `BaseTool` subclass
defined anywhere in the codebase, the instant its module is imported by
anything (even transitively, e.g. through an unrelated test), would have
broken `build_registry()` the same way. This build's `delegate_to_agent`
just happened to be the first thing to trip it.

**Fix:** filter `BaseTool.__subclasses__()` down to only classes whose
`__module__` actually starts with `vinu_agent.tools.` — i.e. only classes
really defined inside the `tools/` package get auto-registered, matching
what `_discover_subclasses()` was clearly always intended to do (it only
*imports* modules from that package's own directory; the bug was that the
class-collection step afterward wasn't scoped to match).

**Proof:** `python -m pytest -q` — 307 passed (was 9 failed before the fix,
same 307 passing after, confirming no other regression).

### 2. `parse_frontmatter()` parsed an empty list `[]` to `[""]`, not `[]`

**What broke it:** `agent/frontmatter.py`'s list-value parsing did
`value[1:-1].split(",")` — for the literal `"[]"`, `value[1:-1]` is `""`,
and `"".split(",")` is `[""]` (a one-item list holding an empty string),
not `[]`. Every `TEAM.md`/`AGENT.md` this build scaffolded uses `tools: []`
or `depends_on: []` to genuinely mean "none" — caught immediately by
`test_team.py::TestLoadAgentSpec::test_parses_frontmatter_and_prompt`
asserting `spec.depends_on == []` and getting `['']` instead. Pre-existing,
not introduced by this build, but this build's markdown files are the
first real, in-repo user of an empty-list frontmatter field.

**Why it wasn't purely cosmetic:** `AgentSpec.tools = list(meta.get("tools",
[]) or [])` — with the bug, an empty `tools: []` became `['']`, a truthy
non-empty list, so downstream `ToolRegistry.subset([''])` silently looked
up a tool named `""`, found nothing, and logged a spurious warning on
every single specialist/manager construction. Harmless in outcome for this
specific empty-list case (ends up with an empty registry either way) but a
real, avoidable footgun for any future non-tools use of empty lists in
frontmatter (e.g. `SKILL.md`'s own list fields).

**Fix:** check whether the bracket contents are empty *before* splitting,
and return `[]` directly in that case.

**Proof:** new regression test `test_skills.py::TestParseFrontmatter::test_empty_list_value`
plus the originally-failing `test_team.py` assertion, both passing.

### 3. Self-introduced: `SessionService.__init__` silently stopped setting `_active_loops`/`_context_builder`

**What broke it:** while wiring `_load_orchestrator_prompt` into `__init__`
earlier in this build, an `Edit` inserted the new `@staticmethod` in the
wrong place — between `self._orchestrator_prompt = ...` and the two lines
that were supposed to follow it (`self._active_loops = {}`,
`self._context_builder = None`). Those two lines ended up physically
*inside* `_load_orchestrator_prompt`, after its own `return body` —
unreachable dead code, and `__init__` silently never set either attribute
on the instance at all.

**Why the existing suite (352/352 at the time) didn't catch it:** every
real user turn goes through `_run_with_agent`, which does
`self._active_loops[session_id] = agent_loop` — that line requires
`self._active_loops` to already exist as a dict; since it never did, this
would have raised `AttributeError` on the very first real message any
session ever received. But nothing in `tests/test_session.py` actually
drives a `role="user"` message through that path: one test hits a
nonexistent session (returns before reaching it), the other uses
`role="assistant"` (the method returns early for non-user roles by
design). A real, pre-existing gap in test coverage, not just bad luck —
this exact class of bug (an attribute only ever touched on the real
end-to-end path) could recur elsewhere the same way.

**Caught by:** manually re-reading the file after an unrelated edit, not
by a test — worth being honest about that rather than implying test
coverage found it.

**Fix:** moved the two attribute-initialization lines back into
`__init__`, closed `_load_orchestrator_prompt` as its own separate method
immediately after them.

**Proof + coverage gap closed:** added
`test_session.py::TestSessionService::test_init_sets_active_loops_and_context_builder`
(asserts the attributes directly, cheap and targeted) and
`test_cancel_current_on_fresh_service_is_false_not_a_crash` (exercises
`self._active_loops.get(...)` for real). Neither requires the full,
heavier `_run_with_agent` integration setup to catch this specific class
of bug again.

### 4. Self-introduced: per-tier LLM config (#11) was reported done but was never actually wired end-to-end

**What broke it:** when #11 was built, `service.py`'s `AgentService.__init__`
was updated to call `SessionService(..., orchestrator_llm=self._orchestrator_llm, ...)`
-- but `SessionService.__init__`'s signature was never actually given an
`orchestrator_llm` parameter. Worse, even setting that aside, the top-level
`AgentLoop` inside `_run_with_agent` still hard-referenced `llm=self._llm`
(the shared client), never `self._orchestrator_llm` -- so even a correct
signature wouldn't have made the feature actually do anything. This was
reported to the user as "Done — 363/363 passing" at the time, which was
true for the suite but false for the feature actually working.

**Why 363 passing tests didn't catch it:** exactly the same root cause as
bug #3 -- nothing anywhere constructs a real `AgentService()`. A
`TypeError: __init__() got an unexpected keyword argument 'orchestrator_llm'`
would only ever surface the first time anyone actually ran the service.

**Caught by:** starting to build the LLM-call-logging feature (this
required looking at `_run_with_agent`'s actual `AgentLoop(llm=...)` call
again), not by a test — same honesty note as bug #3.

**Fix:** added the missing `orchestrator_llm` parameter to
`SessionService.__init__` (falls back to `llm` when not given, matching
`AgentConfig.orchestrator_llm`'s own None-means-shared rule), and changed
the top-level `AgentLoop` to actually use it.

**Proof + coverage gap closed:** added `tests/test_service.py` — the
first test in this codebase that actually constructs `AgentService()` via
its real `__init__`, specifically to catch this class of "wiring exists
on paper but was never exercised" bug going forward. Confirms both the
default (orchestrator shares `_llm`) and configured (orchestrator gets a
distinct instance) cases via object identity, not just non-crashing.

## Deviations from the design doc

### The orchestrator needed no new class, route, or entry point

The design doc described the orchestrator somewhat like a distinct new
component. In practice, the existing `SessionService._run_with_agent`
already builds a plain `AgentLoop` with a full tool registry and a system
prompt for every turn — that *is* the orchestrator, once `delegate_to_team`
is just another auto-discovered tool in that same registry. So:

- No new `AgentService` method, no new route in `server/app.py`.
- `orchestrator/ORCHESTRATOR.md` is real and loaded (not just a doc
  artifact) — its body is appended to the existing system prompt via a
  new `ContextBuilder(orchestrator_prompt=...)` param, so the facilitator
  guidance ("answer directly for simple things, delegate for real
  multi-step work") is actually in the LLM's context, not just implied by
  `delegate_to_team`'s tool description.
- `build_registry()` gained three new injectable params (`llm`,
  `teams_dir`, and a post-construction self-reference `_full_registry`)
  threaded through `SessionService` → `AgentService`, following the exact
  existing DI pattern already used for `skills_loader`/`session_service`/etc.

This is *less* new code than the design doc implied, not more — worth
noting because "additive first" turned out to mean "extend an existing
path," not "build a parallel one," once the actual tool-discovery
mechanism was understood.

### The SSE side-channel needed no new background thread

The design doc specified a background thread (mirroring `swarm/runtime.py`'s
`threading.Thread(target=self._execute_dag, daemon=True)`) pushing status
events onto the session's event bus while `delegate_to_team`'s blocking
tool call was still in flight.

In practice this wasn't necessary: `SessionService._run_attempt` already
runs the *entire* orchestrator turn — the top-level `AgentLoop.run()`, and
therefore anything a tool call does synchronously inside it, including a
team manager's own nested `AgentLoop` and its specialists' — via
`loop.run_in_executor(self._AGENT_EXECUTOR, self._run_with_agent, ...)`,
i.e. already off the FastAPI event loop thread. The existing
`event_callback` → `EventBus.publish(SSEEvent(...))` plumbing (already
built for the orchestrator's own tool-call events) is already safe to call
from that executor thread. So team/specialist progress just needed to
reuse that *same* `event_callback`, tagged per level
(`_tag_event_callback` in `agent/team.py`) so events from the manager and
each specialist are distinguishable from each other and from the
orchestrator's own — no second thread, no new concurrency model.

One real gap this exposed along the way: `build_registry()`'s
`event_callback` parameter existed but was never actually passed a value
at the real call site in `session/service.py::_run_with_agent` (the local
`event_callback` closure was defined *after* the `build_registry(...)`
call, so it could never have reached tools via the injection loop). No
tool before this build declared an `_event_callback` attribute, so nothing
depended on it — this build's `delegate_to_team` is the first thing that
needed it, which is what surfaced it. Fixed by moving the closure
definition above the `build_registry(...)` call and passing it through
explicitly (not a separate bug entry above since it never caused a test
failure — nothing exercised it before now — but recorded here since it's
the same class of "declared but never wired" gap as the others).

## Addition beyond the original design doc: per-tier LLM config

Not something `01-orchestrator-and-teams-architecture.md` originally
specified — added because the orchestrator (the one thing you actually
talk to) may reasonably need a stronger/different provider than teams and
specialists share, e.g. a real OpenAI account for the front-door
conversation while the research team keeps using a cheaper shared local
model for its many internal LLM calls.

- `agent/llm.py`'s `create_llm(config: AgentConfig)` refactored into a
  thin wrapper over a new `create_llm_from_config(llm_config: LLMConfig)`
  — decoupled from needing a whole `AgentConfig`, so any tier can build an
  LLM from just its own `LLMConfig`.
- `AgentConfig.orchestrator_llm: LLMConfig | None = None` — `None` means
  "share `AgentConfig.llm` with teams/specialists," today's behavior,
  unchanged unless you opt in.
- Opt-in is env-var-driven: setting *any* `VINU_ORCHESTRATOR_LLM_*` var
  (provider/model/base_url/api_key/timeout/context_window) builds a
  distinct `LLMConfig` for the orchestrator; fields left unset fall back
  to `LLMConfig`'s own plain defaults, not the shared `VINU_LLM_*` values
  — deliberately, since mixing a shared local model's name with a
  different provider would be silently wrong, not just incomplete.
  Documented in `vinu-components/.env-example`.
- `AgentService` builds `self._orchestrator_llm` once at startup (falls
  back to `self._llm` when unconfigured) and passes it into
  `SessionService` as a new, separate `orchestrator_llm` param. Only the
  orchestrator's own top-level `AgentLoop` uses it —
  `build_registry(llm=self._llm, ...)` (what `delegate_to_team` ends up
  using to build teams/specialists) is untouched, so teams/specialists
  always use the shared config regardless of what the orchestrator is set
  to.
- Tests: `tests/test_config.py` (new — `_load_orchestrator_llm_config`'s
  opt-in trigger and field fallback behavior), additions to
  `tests/test_llm.py` (`create_llm_from_config` standalone usability).

## Addition beyond the original design doc: every-LLM-call logging

User ask: every LLM call, anywhere in the system, should have its full
prompt, response, token counts (sent/received), and latency stored — so
context usage can be understood empirically from real calls, not guessed
at from aggregate counts.

**What already existed and wasn't enough:** `agent/loop.py` already had
`_record_llm_telemetry()`, recording token counts and latency into
`telemetry.db` via the shared `vinu_infra.telemetry` module. Two real
gaps: it never stored the actual prompt content (only counts), and it's
only called from the main loop's `_call_llm` — `_auto_compact` and
`_iterative_update` (the context-compaction summarization calls) call
`self.llm.chat(...)` directly and were never recorded at all.

**Design:** a transparent wrapper, not another call-site-by-call-site
recording function — catches every call regardless of who makes it or
whether they remember to log it.

- [`storage/llm_calls.py`](../../vinu-components/vinu-agent/vinu_agent/storage/llm_calls.py)
  — `LlmCallLogStore(SQLiteBackend)` + `LlmCallRecord`. A new, dedicated
  store (not an extension of the shared `vinu_infra.telemetry` schema
  other services also use) — full prompt (`prompt_json`) and response are
  genuinely large per-row content, scoped to just this need rather than
  bloating shared infrastructure. Includes `total_tokens_by_tier()` — the
  actual aggregate query this exists to answer.
- `agent/llm.py::LoggingChatLLM` — wraps any real `ChatLLM`; on every
  `.chat()` call, records the full prompt, response, token usage (real if
  the provider reports it, estimated via the same char/4 heuristic
  `agent/loop.py` uses otherwise — so numbers are comparable), latency,
  and success/error, then forwards the response through unchanged.
  Logging failures are swallowed (never break the real LLM call) — same
  discipline as `vinu_infra.telemetry`'s `record_*_safe()` functions.
- `agent/llm.py::wrap_with_logging(llm, store, **tags)` — the actual
  integration point; a no-op passthrough when `store` is `None`, so every
  call site can call it unconditionally with no `if store:` guard.
- **Tagged per call site, not per LLM client instance** — mirrors the
  exact same reasoning as the SSE `_tag_event_callback` pattern: since
  the same underlying `self._llm` is shared across every team/specialist,
  a wrapper instantiated once centrally couldn't know which agent made
  which call. Instead, `wrap_with_logging(...)` is called fresh at each
  of the three real construction sites — the orchestrator's own loop
  (`tier="orchestrator"`), a team manager's loop
  (`tier="manager", team=...`), and each specialist's loop
  (`tier="specialist", team=..., agent=..., role=...`) — cheap (just
  wraps the same real client with different tags), and every row in the
  log says exactly who made that call.
- `llm_call_store` threaded through the identical DI chain already
  established for `run_store`: `AgentService` → `SessionService` →
  `build_registry()` → `DelegateToTeamTool` → `TeamManager` →
  `DelegateToAgentTool`.

This is also what surfaced bug #4 above — building this required looking
at `_run_with_agent`'s real `AgentLoop` construction again, which is where
the orchestrator_llm wiring gap was actually found.

**Tests:** `tests/test_llm_calls_storage.py` (new — storage round-trip,
filtering, aggregation), additions to `tests/test_llm.py`
(`LoggingChatLLM`/`wrap_with_logging` — forwards responses unchanged,
logs provider-reported vs. estimated tokens correctly, records failures
and still re-raises, logging failures don't break the real call,
attribute proxying), addition to `tests/test_team.py` (end-to-end: a
manager + one specialist call each get logged with distinct, correct
tier/team/agent/role tags), addition to `tests/test_tools_discovery.py`
(`llm_call_store` injection).
