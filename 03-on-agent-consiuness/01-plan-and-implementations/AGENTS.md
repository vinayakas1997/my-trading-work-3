---
name: agents
status: definition-phase
purpose: single source of truth for turning 03-on-agent-consiuness's audit (01/02) and reference-pattern research (03) into actual implementation in vinu-components — what gets built, in which files, in what order, before any code is written. Nothing described in this folder has been built yet.
---

# Agent Consciousness — Implementation Plan

**This is a definition document, not an implementation log**, same discipline
as `02-the-1-month-back-testing/full-plan.md`. Scope and file targets are
fixed up front so an agent picking this up doesn't have to re-derive
architecture decisions or re-read the whole audit trail cold.

## Why this exists

The 1-month replay (`02-the-1-month-back-testing/`) proved the
infrastructure works but exposed that `vinu-agent` has no real
"consciousness" layer: it went silent for 16 of 20 simulated days and, on
one of those silent days, fabricated a stock price and repeated it
confidently for 13 straight days. `03-on-agent-consiuness/01-quant-agent-
qualities.md` defined what a real quant agent needs; `02-vinu-components-
where-how.md` mapped that onto this codebase and found the gaps; `03-
advanced-patterns-from-reference-repos.md` found working answers for those
gaps in `personal-important/other-reference-repos/Vibe-Trading` and
`ref-fincept-terminal`. This folder is where those answers become an actual
build plan — the fourth and final step before anything gets touched in
`vinu-components`.

**Read `../00-start-here.md` first if you haven't** — it has the full
context chain (01 → 02 → 03) this plan assumes as already established.

## The four items — one-line summary, full detail per file

| # | Item | Solves (from 02's gap list) | Reference pattern (from 03) | Status |
|---|---|---|---|---|
| 1 | [Fact-verification / anti-fabrication audit](01-fact-verification-audit.md) | fabricated JNJ price, no fact-vs-belief distinction | `report_audit_tool.py` (Vibe-Trading) | Implemented |
| 2 | [Forced ground-truth injection](02-forced-ground-truth-injection.md) | tool-call dropout, no forced daily ritual | `grounding.py` (Vibe-Trading) | Implemented |
| 3 | [Structured decision journal](03-structured-decision-journal.md) | no structured decision/outcome record | `HypothesisRegistry` + thesis-tracker (Vibe-Trading) | Implemented |
| 4 | [Audit-log event schema](04-audit-log-schema.md) | no "what happened when" trail; verifies governors are actually wired in | `AuditLogger` schema (ref-fincept-terminal) | Implemented |

This is the same priority order `03`'s "Recommendation" section already
settled on, for the same reason: items 1-2 directly prevent a repeat of the
two concrete replay failures, item 3 closes the learning loop those two
failures showed doesn't exist, item 4 is cheap plumbing the other three can
log into.

**Explicitly not a plan item**: hard escalation / confidence-thresholding
(the agent genuinely refusing to answer below some confidence bar). `03`
confirmed this is unsolved in all six reference repos, not just
`vinu-components` — it's a real, harder design problem that deserves its
own dedicated pass later, not a fifth item bolted onto this batch.

## Important context already established — don't re-derive this

- **Consciousness before more skills.** `01-quant-agent-qualities.md`'s own
  ordering: a skilled agent with no discipline is a liability with good
  vocabulary. None of these four items add a new trading capability — they
  govern the ones that already exist (`generate_trade_plan`, bracket
  orders, portfolio-aware sizing already in `trade_plan_tool.py` per `02`).
- **`TradingMandate`/`OrderGuard` (`vinu_agent/broker/mandate.py`) is the
  one governor confirmed to actually work today** — built, and genuinely in
  the live order call path, unlike `ref-fincept-terminal`'s `RiskManager`/
  `ConfirmationService` (built, never called — see `03`). Item 4's first
  concrete task is re-confirming this by grep before building anything new,
  precisely because "built but never wired in" turned out to be a common,
  repeatable mistake in the reference repos.
- **Tool instances already receive per-session attributes via `hasattr`
  injection**, not constructor arguments (`vinu_agent/tools/__init__.py:26-
  51`, `build_registry()`). Item 2's ground-truth injector and any new
  per-session state these items need should follow this existing pattern,
  not invent a new wiring mechanism — same rule item 1 of the backtest plan
  followed for `_as_of`.
- **`ContextBuilder` (`vinu_agent/agent/context.py`) has no compaction or
  tagging logic of its own** — it assembles system prompt + raw history +
  current message. Item 2's injection point is here, not inside
  `AgentLoop`.
- **`AgentLoop.run()` (`vinu_agent/agent/loop.py`) is where the final
  assistant message is composed and returned**, and where the wrap-up-nudge
  / context-compaction logic already lives. Item 1's audit hook plugs in
  here, after the response is composed and before it's persisted or
  returned.
- **The failure this whole folder responds to is documented with exact
  quotes and line-level evidence in `the-project-vision/the-premarket-
  agents-answers-from-replay.md`** — re-read that before implementing item 1
  or 2, it's the concrete reproduction case each fix should be checked
  against.

## Execution order — recommended, not mandatory

1. **Item 2 first** (forced ground-truth injection) — structurally the
   simplest ("inject data before reasoning starts," no new persistence
   layer) and it's the one that would have prevented the tool-call dropout
   from mattering in the first place, since fresh data would already be in
   context regardless of whether the model chooses to call a tool.
2. **Item 1** (fact-verification audit) — the safety net for whatever gets
   past item 2 anyway (the model can still misstate a number that *was* in
   context). Independent of item 2's plumbing, can be built in parallel.
3. **Item 3** (structured decision journal) — depends on items 1-2 being in
   place first: a journal fed by ungrounded, unverified reasoning is not
   worth building.
4. **Item 4** (audit-log schema) — build alongside or after item 3; it's the
   lower-level log underneath the higher-level journal, and its first task
   (confirm `TradingMandate` is genuinely wired in) has no dependency on
   the other three and can be done anytime.

## How to verify each item — general rule

Same rule as the backtest plan: verify against the real running
`vinu-components` stack, not synthetic fixtures alone. Every one of these
items touches code in the shared `AgentLoop`/`ContextBuilder`/session path
that live (non-replay) sessions also use — after each change, re-verify a
normal session still behaves identically to before. Once an item is
actually built and verified, **update its status here and in `02-vinu-
components-where-how.md`'s gap table** — that file is the source of truth
for "what's actually true of the codebase today" and must not go stale.

## Related documents

- [../00-start-here.md](../00-start-here.md) — entry point, read first.
- [../01-quant-agent-qualities.md](../01-quant-agent-qualities.md) — the
  framework each item is grounded in.
- [../02-vinu-components-where-how.md](../02-vinu-components-where-how.md)
  — the gap table these items close; **update this when an item ships.**
- [../03-advanced-patterns-from-reference-repos.md](../03-advanced-patterns-from-reference-repos.md)
  — where each item's reference pattern was found, with file:line citations
  into the actual reference-repo code.
- [../../the-project-vision/the-premarket-agents-answers-from-replay.md](../../the-project-vision/the-premarket-agents-answers-from-replay.md)
  — the concrete failure evidence items 1-2 are built to prevent.
