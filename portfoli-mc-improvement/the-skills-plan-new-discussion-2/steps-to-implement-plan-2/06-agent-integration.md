---
name: 06-agent-integration
status: Not Started
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

*(To be filled in after implementation.)*

## Definition of done

- [ ] Current loop fully read and understood.
- [ ] Integration approach chosen, designed, and documented.
- [ ] Integration implemented (skills loadable, agent can compose plan).
- [ ] Governor constraints enforced at loop level.
- [ ] Tests cover skill discovery, content retrieval, governor enforcement.
- [ ] System skill doc updated.

## Open risks / assumptions

- The 128k context limit is a real constraint. Pre-loading all skills
  (Option A) could consume 20-40k tokens before any work starts. Verify
  total skill size before committing to an approach.
- The existing 50-iteration cap directly constrains how long an agent
  session can run. Multi-session resumability (using Step 02/07's
  checkpoint/hypothesis tools) may be needed for long-running research.
  This was designed in the first plan (governor + SQLite lineage) but
  never implemented at the loop level — flag if needed.
