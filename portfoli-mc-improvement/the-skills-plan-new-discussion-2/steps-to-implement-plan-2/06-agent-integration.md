---
name: 06-agent-integration
status: Completed
phase: 4
code: D6
depends_on: [01-stage-skills]
unlocks: [07-validation]
---

# Step 06 — Agent Integration: Skills at Runtime

## Why this step

The entire philosophy of this project is **"skills are a knowledge library,
not scripts — the agent composes them at runtime."** But the agent's ReAct
loop (`vinu_agent/agent/loop.py`) has never been modified to do this. It
has a 50-iteration cap, context management (microcompact/collapse/auto-compact),
and a fixed tool registry — but no mechanism to "read all skills, compose a
plan, execute it, check against the governor, loop."

All the intelligence built in the first plan (gatekeepers, sweep rules,
governor, daily allocation) exists as files on disk. The agent cannot use
any of it autonomously.

## What we're achieving

- The agent's loop can read all available skills at startup (or on demand).
- The agent can compose a plan from skills, execute it via tools, check
  progress against the governor, and loop — without a hand-written script.
- This is the final piece that makes the system truly self-agentic.

## Where it matters in the future

Without this step, everything built is manually invocable but not
autonomous. With it, the agent can wake up, read its library, understand
what's available, and decide what to do — the original vision.

## How it connects to other steps

- **Depends on Step 01** — skills must be in `vinu-agent/skills/` before
  the agent can read them.
- **Independent of Steps 02-05** — can be designed and built in parallel
  with the game-plan work, as long as skills are live.
- **Unlocks Step 07** — full validation requires the agent to run
  autonomously.

## Substeps

1. **Read the current loop.** Re-read `vinu_agent/agent/loop.py` in full.
   Understand:
   - The ReAct cycle: Plan → Tool Call → Observe → Repeat.
   - The 50-iteration cap and 80%-budget wrap-up nudge.
   - Context management (microcompact at 50%, collapse at 70%, auto-compact
     at 128k).
   - How skills are currently loaded (if at all) — `load_skill_tool.py`
     exists but is it called? By what?
   - How the governor's constraints (from Step 08) should be checked at
     each iteration.

2. **Design the integration.** Define:
   - When are skills loaded? (At startup? On demand? First time a skill
     reference is encountered?)
   - How does the agent signal "I need to consult a skill"? (A tool call?
     A system prompt injection? A pre-read context block?)
   - How does the governor check happen? (Agent checks itself? A separate
     tool returns "should I stop?" Hard limit enforced at the loop level?)
   - How does the plan-compose step work? (The agent reads relevant skills
     for its task, then produces a plan in structured form, then executes
     it — is this a new tool, or just a reasoning step in the loop?)

3. **Implement the minimal integration.** The goal is the smallest change
   that makes the philosophy real. Options:
   - Option A: Pre-load all skills into the system prompt at loop start.
     Simplest, but uses tokens — skills are large.
   - Option B: Add a `read_skill(name)` tool the agent can call when it
     needs context. More efficient, requires the agent to know to call it.
   - Option C: Inject skill summaries at loop start, full text on request.
     Balanced approach.
   Choose based on the 128k context limit and the number of skills.

4. **Wire the governor.** Ensure the hard limit (max iterations, max
   wall-clock) is enforced at the loop level, and the progress/expectancy
   heuristics are available as tools the agent can call to check "should
   I continue?"

5. **Write tests.** Test that skills are discoverable, that the read_skill
   tool (or equivalent) returns expected content, and that the governor
   limit stops execution appropriately.

6. **Update skill docs.** Document how the agent uses skills at runtime
   in a system-level skill (e.g. `agent-self/SKILL.md` update) so any
   future agent build picks up the convention.

## What was actually built

Most of substeps 1-3's design (Option C: on-demand `load_skill` +
`plan_workflow`/`complete_step` for multi-skill tasks, wired through
`WorkflowTracker` and `build_registry()`) already existed uncommitted
before this session. What was actually missing was (a) a real bug that
silently broke the whole path in production, (b) end-to-end test
coverage, and (c) the governor DoD item never being traced against what
`governor/SKILL.md` (from the first plan) actually specifies.

- **The blocking bug (found while starting this step, fixed first since
  it undermined this step's entire premise):** `build_registry()`
  (`vinu_agent/tools/__init__.py`) only injects a dependency when
  `hasattr(tool, "_x")` is `True` *before* injection. `LoadSkillTool`,
  `RememberTool`, `SessionSearchTool`, `QueryMemoryTool`,
  `CompleteStepTool`, and `PlanWorkflowTool` only referenced their
  dependency via `getattr(self, "_x", None)` inside `execute()`, with no
  `__init__` declaring a default — so the `hasattr` check was always
  `False` and injection silently never fired, even though
  `session/service.py::_run_with_agent` was already passing real
  `skills_loader`/`unified_memory`/`session_service`/`workflow_tracker`
  values into `build_registry()`. Fixed by adding `__init__` to each tool
  setting its dependency attribute to `None`, matching the existing
  `_services_config = {}` convention. Full trace in this file's AGENTS.md
  entry.
- **Substep 1 (read the loop):** confirmed the ReAct cycle, the
  50-iteration cap + 80%-nudge, the 3-tier context management, and that
  `AgentLoop` already carries its own `WorkflowTracker` instance
  (`self._workflow_tracker`), which `service.py` overwrites with the same
  instance passed into `build_registry()` — so the loop's
  `<workflow>`-block rendering and the tools' state mutation already
  operate on one shared object, not two copies.
- **Substep 2/3 (design + minimal integration):** Option C was already
  chosen and built — `load_skill` is on-demand (not preloaded), and
  `plan_workflow`/`complete_step` let the agent declare and progress
  through a multi-skill plan, with the tracker's state rendered into the
  system prompt every iteration via `WorkflowTracker.to_context_block()`.
- **Substep 4 (governor wiring) — traced, not built, with rationale:**
  `governor/SKILL.md` (written for the first plan's Step 08, paired with
  `optimizer-rules`) explicitly documents that its Layer 1 hard limit
  **is** the ReAct loop's `max_iterations` cap — already real, already
  enforced (`while iteration < self.max_iterations`), confirmed by
  reading that skill's own text against `loop.py`. Layer 2's adaptive
  heuristics (progress, expectancy) are, by that same skill's explicit
  design, **not** meant to be loop-level code — they're logic the agent
  applies itself by reading the hypothesis/evidence trail through
  existing tools (`query_hypotheses`/`add_hypothesis_evidence`), matching
  this plan's "skills are a knowledge library, not scripts" principle
  throughout. No `governor.py` module enforcing Layer 2 was built, and
  none is needed for this DoD item to be honestly checked — the intended
  design was already documented before this step touched it, and this
  step traced it rather than silently assuming a gap or silently building
  unwanted code. Written up in `agent-self/SKILL.md`'s new "Governor"
  section so this reasoning isn't lost.
- **Substep 5 (tests):** `tests/test_agent_integration.py` (new) —
  end-to-end test using a real `build_registry()` (with a real
  `SkillsLoader` pointed at `vinu-agent/skills/`) and a real `AgentLoop`,
  scripted through `plan_workflow` → `load_skill` → `complete_step`,
  asserting: `load_skill` returns real file content (not a DI-bug "not
  available" error), the shared `WorkflowTracker` reaches
  `all_completed()`, and the loop actually injects a live `<workflow>`
  block into an LLM call mid-run — not just that the tracker object looks
  right after the fact. Plus a negative-path test confirming a registry
  built with no `skills_loader` fails cleanly. `test_tools_discovery.py`
  (Step 06's DI-fix prerequisite) separately covers injection at the unit
  level for all six previously-broken tools.
- **Substep 6 (skill doc):** `agent-self/SKILL.md` updated with sections
  on how skills/workflow tools work at runtime, the DI bug and its fix,
  and the governor-tracing finding above.

## Definition of done

- [x] Current loop fully read and understood.
- [x] Integration approach chosen, designed, and documented.
- [x] Integration implemented (skills loadable, agent can compose plan).
- [x] Governor constraints enforced at loop level — Layer 1 (hard limit)
      confirmed enforced; Layer 2 (heuristics) confirmed intentionally
      agent-composed, not loop-level, per `governor/SKILL.md`'s own
      design. See "What was actually built" for the trace.
- [x] Tests cover skill discovery, content retrieval, governor enforcement
      (Layer 1's `max_iterations` cap already had coverage in
      `test_loop.py::test_max_iterations_reached`; skill/workflow
      discovery and retrieval now covered by
      `test_agent_integration.py`).
- [x] System skill doc updated.

## Open risks / assumptions

- The 128k context limit is a real constraint. Pre-loading all skills
  (Option A) could consume 20-40k tokens before any work starts. Verify
  total skill size before committing to an approach.
- The existing 50-iteration cap directly constrains how long an agent
  session can run. Multi-session resumability (using Step 02/07's
  checkpoint/hypothesis tools) may be needed for long-running research.
  This was designed in the first plan (governor + SQLite lineage) but
  never implemented at the loop level — flag if needed.
