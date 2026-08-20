---
name: implementation-plan-index
status: roadmap, ready to hand to any implementing agent
purpose: ordered, self-contained task list closing the gaps found in 01-vinu-components-shortcomings.md and porting the logic identified in 02-reference-repos-core-logic.md. Each task file is meant to be readable and actionable on its own, without needing this conversation's history.
---

# Implementation plan — index

Source of truth for *why* each task exists:
- `../01-vinu-components-shortcomings.md` — code-verified gaps (audited directly against `/home/somic_cps/Vina/my-trading-work-3/vinu-components`, not doc-guessed)
- `../02-reference-repos-core-logic.md` — what to port from the two reference repos, with tradeoffs

Every task below follows the same shape: **Goal / Why / Current state (verified) / Steps / Acceptance criteria / Dependencies**.
An implementing agent should read a task file, verify the "current state" claims are still true by
reading the actual files cited (code may have moved on since this audit), then implement.

## Task list, in recommended order

| # | File | Closes | Est. effort | Depends on |
|---|------|--------|--------------|------------|
| 10 | [10-structured-logging.md](10-structured-logging.md) | production-grade gap: no error visibility | medium | none — **land first** |
| 11 | [11-service-auth.md](11-service-auth.md) | production-grade gap: no auth on any route | medium | task 10 (auth failures need somewhere to log to) |
| 1 | [01-schedule-capital-allocator.md](01-schedule-capital-allocator.md) | Shortcoming #1 | small | task 10, 11 (new unattended worker should be born with logging+auth) |
| 2 | [02-schedule-shadow-evaluator.md](02-schedule-shadow-evaluator.md) | Shortcoming #2 | small | task 10, 11 |
| 3 | [03-significance-triage-notifications.md](03-significance-triage-notifications.md) | Shortcoming #4 | small (config only) | none |
| 4 | [04-rebalance-cross-process-route.md](04-rebalance-cross-process-route.md) | Shortcoming #3 | medium | task 10, 11 (new cross-service route should be born with logging+auth) |
| 5 | [05-position-sizing-risk-gatekeeper.md](05-position-sizing-risk-gatekeeper.md) | Shortcoming #7 | medium | none |
| 6 | [06-walk-forward-validation.md](06-walk-forward-validation.md) | Shortcoming #8 | medium | none |
| 7 | [07-llm-provider-fallback.md](07-llm-provider-fallback.md) | Shortcoming #9 | small | none |
| 8 | [08-live-llm-validation-tests.md](08-live-llm-validation-tests.md) | Shortcoming #5 | medium | tasks 5, 6 should land first so there's something real to validate |
| 12 | [12-decimal-audit.md](12-decimal-audit.md) | production-grade gap: float on the money path | medium | none |
| 13 | [13-secrets-management.md](13-secrets-management.md) | production-grade gap: secrets only in .env | medium | loosely coupled with task 11 |
| 9 | [09-doc-reality-fixes.md](09-doc-reality-fixes.md) | Shortcoming #6 | trivial | do last, once everything above lands (docs should describe final state) |

## Ordering rationale

**Tasks 10 and 11 are cross-cutting foundation and come first, ahead of everything else**, including the
original 1-9 numbering. They were added after the original plan was written, once a direct grep audit
found zero structured logging and zero authentication anywhere in `vinu-components`. The reason they lead
rather than append: tasks 01 and 04 add new unattended workers and a new cross-service HTTP route — if
logging and auth land after those, the new work ships unmonitored and unauthenticated and then needs
retrofitting. Landing 10 and 11 first means every subsequent task inherits them for free, the same way
this project already treats Kill Switch and fail-closed defaults as things built in from day one rather
than added later.

Tasks 1-3 are pure scheduling/config wiring — same pattern already proven six times over in
`vinu-agent/entrypoint.sh` (planner-worker, significance-worker, skill-audit-worker, trade-plan-worker,
feedback-worker, shadow-worker). Lowest risk, highest immediate value: real logic currently sitting
behind a manual trigger starts running unattended. Do these once 10/11 are in place.

Task 4 (rebalance cross-process route) is medium effort because it's genuinely new wiring between two
services (vinu-agent's capital_allocator and vinu-live's orchestrator), not just adding a worker process.

Tasks 5-7 are the capability gaps identified against the two reference repos — net-new logic, not just
wiring. Independent of each other, of 1-4, and of 10/11; can be done in parallel by different agents at
any point.

Task 8 depends on 5 and 6 landing first, since there needs to be new prompt/logic behavior worth
validating against a live LLM (the existing untested behaviors — idea_generator's recipe-first
preference, Phase 8's consensus prompt — are also fair game to validate now if 5/6 aren't ready yet).

Tasks 12 (Decimal audit) and 13 (secrets management) are real production-grade gaps but lower urgency
than 10/11 — they don't get retrofitted by other in-flight work the way an unauthenticated new route
would, so they can land any time, ideally before real capital or real broker credentials are involved.

Task 9 is cleanup — fix the two docs that understate/misstate what's actually built, done last so it
reflects the final, not intermediate, state.

**Deferred, not yet scoped:** a Jarvis-like watcher-agent that polls system health and decides what's
worth surfacing, sitting on top of task 10's logging substrate the way Significance Triage sits on top of
TickerLedger. Mentioned in conversation but intentionally not written up as a task yet — needs task 10 to
exist first, and the exact design is still being thought through.

## Ground rules for whoever implements these

- **Verify before building.** Every task file cites file:line evidence from an audit performed on
  2026-08-17. Code moves. Re-grep/re-read the cited files first; if something's changed, note it and
  adjust rather than building against a stale assumption.
- **Follow the existing patterns.** This codebase already has a consistent worker-process pattern
  (`entrypoint.sh` + a `*_worker_main` function in `cli.py`), a consistent hook pattern
  (`*_hook.py` files doing manager-level, non-agent-callable state transitions), and a consistent
  tool-auto-discovery pattern (`tools/__init__.py` registers any `BaseTool` subclass automatically —
  do not hand-register new tools). Match these, don't invent new ones.
- **Traceability discipline.** This project has repeatedly required every decision (funding, gating,
  sizing) to report a specific, stored reason — never a black-box number. Any new logic (position
  sizing, walk-forward verdicts) must follow the same discipline: log what informed the number.
- **Fail-closed by default.** Existing gates (sweep completeness threshold, Kill Switch) treat
  uncertain/incomplete data as a hard FAIL, never a lenient pass. New gates should match this posture
  unless a task file explicitly says otherwise.
