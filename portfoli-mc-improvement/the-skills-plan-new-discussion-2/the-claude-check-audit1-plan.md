Ready for review
Select text to add comments on the plan
Properly Completing steps-to-implement-plan-2
Context
Discussion-2's plan is a 7-step gap-closing plan sitting on top of discussion-1's work. I verified it against the actual repo (vinu-components/) rather than trusting the docs, and found two things:

The process log is stale, not the code. Steps 04 (daily game plan) and 05 (risk budget) are functionally implemented, wired, and passing tests — game_plan.py and risk_budget.py are both integrated into PortfolioService and exposed via GET /daily-game-plan — but AGENTS.md and 00-overview.md's phase table still say "Not Started" for both. Step 06 is half-wired: WorkflowTracker is in the loop, two new tools exist, but nothing registers them correctly (see next point).

A real, verified bug blocks Step 06's entire premise. build_registry() in vinu_agent/tools/__init__.py injects dependencies like this:

if skills_loader and hasattr(tool, "_skills_loader"):
    tool._skills_loader = skills_loader
This only fires if the tool already has that attribute before injection. Tools that rely on self._services_config = {} set in __init__ (the convention used by ~15 tools, e.g. correlation_tool.py) work fine. But LoadSkillTool, RememberTool, SessionSearchTool, and the two brand-new CompleteStepTool/PlanWorkflowTool never set a default in __init__ — they only do getattr(self, "_x", None) inside execute(). I confirmed with a direct interpreter check that hasattr() is False for all five before injection, which means the conditional never fires and every one of these tools silently returns "not available" in production, even though vinu_agent/session/service.py does pass real skills_loader, unified_memory, session_service, and workflow_tracker values into build_registry(). There is no test that exercises this path end-to-end (test_tools_discovery.py only covers _services_config), which is why it's gone unnoticed.

Practically: the agent cannot currently read skills, remember things, search past sessions, or use the new workflow tools at runtime — the exact capability Step 06 exists to deliver. This is not a design gap the step file anticipated; it's a pre-existing wiring bug that also silently undermines Step 01's "Completed" status.

The goal of this plan is to close every remaining item honestly: fix the root cause, finish the two under-documented-but-actually-done steps properly (against their real Definition of Done checklists, not just "tests pass"), finish Step 06 for real, then do Step 07 (validation), and leave the docs in a state that matches reality.

Approach
1. Fix the dependency-injection bug (blocking, do first)
Add a __init__ that pre-declares the attribute as None, matching the existing _services_config = {} convention, in:

vinu-agent/vinu_agent/tools/load_skill_tool.py (self._skills_loader = None)
vinu-agent/vinu_agent/tools/remember_tool.py (self._unified_memory = None)
vinu-agent/vinu_agent/tools/session_search_tool.py (self._session_service = None)
vinu-agent/vinu_agent/tools/complete_step_tool.py (self._workflow_tracker = None)
vinu-agent/vinu_agent/tools/plan_workflow_tool.py (self._workflow_tracker = None)
Also check query_memory_tool.py (it matched the earlier grep for _unified_memory/_persistent_memory — read it before assuming it needs the same fix or already has it).

Add a regression test in test_tools_discovery.py mirroring test_build_registry_with_services_config, but for skills_loader, unified_memory, session_service, and workflow_tracker — asserting the tool's private attribute is actually the injected object after build_registry(...), not just that construction doesn't crash. This is the test that should have caught the bug; without it the fix can regress silently again.

2. Reconcile the documentation with reality (Steps 01, 04, 05)
In AGENTS.md, append proper entries under the 04-daily-plan-document and 05-risk-budget headings describing what's actually there today (game_plan.py, risk_budget.py, their wiring into service.py, the route, the existing tests) — dated as a past session, not invented as "just finished," since the code already exists uncommitted.
Update 00-overview.md's phase table rows for 04 and 05, and each step file's own frontmatter status: field, once their Definition of Done checklists are actually fully checked (see next sections — they're not quite there yet).
Add a short note to the 01-stage-skills entry (or a new dated entry) documenting the DI bug found and fixed, since it directly concerns the "skills are usable" claim that step made.
3. Finish Step 04 (daily plan document) against its real DoD
Read game_plan.py, service.py::compute_daily_game_plan, and test_game_plan.py fully, then check each unchecked box:

 Readiness score correctly reflects degraded sources — verify the formula counts live vs. failed-open data sources per the step file's substep 1 definition (not just "score exists").
 Tests cover the empty-portfolio and all-data-unavailable edge cases explicitly (step file substep 4) — check test_game_plan.py for these cases by name; add them if missing.
 daily-allocation/SKILL.md updated to describe the unified plan and readiness score (substep 5) — check the file; it's likely untouched since this wasn't logged anywhere.
Only flip status to Completed once all six DoD boxes are genuinely checked.

4. Finish Step 05 (risk budget) against its real DoD
Read risk_budget.py and test_risk_budget.py fully, then check:

 Regime-tightening logic (REGIME_SIZING_MULTIPLIERS) has direct test coverage for the tightening formula from the step file's research notes, not just tier thresholds.
 Tests cover budget breach and regime-shift tightening as distinct cases (step file substep 5).
 live-safety/SKILL.md and daily-allocation/SKILL.md updated (substep 6) — check; likely untouched.
 Confirm DailyPositionTracker is fed real intraday P&L in production (the step file's own "Open risks" section flags this as unverified) — trace where compute_risk_budget() is called with real positions data vs. a fresh tracker, and note the answer in the AGENTS.md entry either way.
5. Finish Step 06 (agent integration) for real
With the DI bug fixed (step 1), the actual remaining work is thin:

Verify end-to-end (not just unit-level) that a real build_registry() + AgentLoop run lets the agent call load_skill, plan_workflow, and complete_step and see the effects (e.g. the <workflow> context block updates after complete_step). Write one integration test doing this, since none currently exists.
Governor enforcement: the step file's DoD requires "governor constraints enforced at loop level" — check whether loop.py actually calls anything from the Step 08 governor (hard limit / progress / expectancy heuristics) beyond the existing max_iterations cap. If it doesn't, this is a real gap to close, not just a doc gap — decide with the user whether to scope it in or explicitly defer it with a documented reason.
Update the system-level skill doc describing how the agent uses skills/ workflow tools at runtime (DoD's last box).
6. Step 07 (validation) — scope check before building
This step is genuinely unstarted and is the biggest remaining chunk of new work (historical simulation script + ShadowEvaluator paper-trading run). Before writing code: confirm with the user whether they want the full historical-simulation script built now, or whether — given steps 04-06 need to land and be trusted first — this should be scoped as a separate follow-up once 01-06 are solid. I'll ask this directly via clarifying question before starting Step 07 work, rather than assume.

7. Commit
Once a coherent chunk of the above is done and tests pass, stage and commit with a clear message — but only after confirming with the user, per the project's git safety rules; nothing here should be force-pushed or squashed.

Verification
Run each affected repo's test suite after every change: pytest vinu-agent/tests/ -q, pytest vinu-portfolio/tests/ -q, pytest vinu-research/tests/ -q, pytest vinu-live/tests/ -q.
For the DI bug fix specifically: run the new regression test, then manually instantiate build_registry(skills_loader=<fake>, ...) and assert registry.get("load_skill")._skills_loader is the fake object — this is the exact check that was missing before.
Re-run the full cross-repo suite at the end and compare pass counts against the current baseline (portfolio 89, live 118, agent 218, research 535 passed/1 skipped/1 pre-existing unrelated flake in test_sqlite_backend.py::TestThreadSafety::test_concurrent_writes) to catch regressions.
Add Comment