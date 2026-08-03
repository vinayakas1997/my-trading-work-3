---
name: fact-verification-audit
component: vinu-agent
status: implemented
---

# Item 1 — Fact-Verification / Anti-Fabrication Audit

## Where to fetch the details

- Reference pattern, read in full: `personal-important/other-reference-
  repos/Vibe-Trading/agent/src/tools/report_audit_tool.py` (extract→verdict
  two-phase audit) and `financial_rigor_tool.py` (`cross_validate`,
  exact-Decimal arithmetic for the numeric side) — summarized in
  `../03-advanced-patterns-from-reference-repos.md` §"Fact-vs-belief /
  anti-fabrication."
- The concrete failure this closes: `../../the-project-vision/the-
  premarket-agents-answers-from-replay.md`, Section 1's JNJ finding — on
  2026-07-09 the agent stated `$162.45` for JNJ with no tool call that day
  and no matching value anywhere in the session's tool-response history
  (real anchor one day earlier: `$267.16`, confirmed via `get_stock_price`).
  That fabricated number then repeated verbatim for 13 consecutive days,
  formatted identically to genuine tool output.
- Codebase gap this fixes: `../02-vinu-components-where-how.md`'s "fact vs
  belief distinction" row (tagged ❌ missing, → see 03).

## Why

Nothing in `vinu-agent` today checks whether a number in its own final
answer actually came from a tool call this session. The replay proved this
isn't a hypothetical: the model produced a plausible, decimal-precise,
confidently-formatted price it never fetched, and nothing caught it before
it became part of the session history the next 13 days built on top of.

## Impact

This is the highest-leverage single fix in this plan. It doesn't require
knowing *why* the model fabricates (token pressure, dropped tool calls,
plain hallucination) — it catches the symptom structurally, after the fact,
regardless of cause. It's also the cheapest of the four items to justify:
a post-hoc check bolted onto the existing loop, no core-loop redesign.

## What decision-dots this connects to for the future

- Makes `01-quant-agent-qualities.md`'s "calibrated self-doubt" quality
  concrete for the first time — a real "verdict: FAIL, unverifiable claim:
  X" signal is the input a future escalation/confidence mechanism would
  need, even though that mechanism itself is explicitly out of scope here
  (see `AGENTS.md`).
- Becomes the natural place to plug in a future critic/second-opinion role
  if one is ever built (`ref-FinRobot`'s leader/worker pattern, noted in
  `03` as not a current priority but worth remembering for later).
- Should share its verdict log with item 4's audit-log schema rather than
  inventing its own separate log format.

## Implementation

Two-phase, mirroring `report_audit_tool.py`:

1. **Extract phase** — after `AgentLoop.run()` composes the final assistant
   message (`vinu_agent/agent/loop.py`), scan it for numeric claims tied to
   a symbol: prices, %-changes, quantities, dates. Regex-based extraction
   first (cheap, matches the reference implementation's approach); an
   LLM-based extraction pass is a possible fallback if regex misses
   phrasing, not a first-pass requirement.
2. **Verdict phase** — for each extracted claim, check whether a matching
   value (same symbol, within ~1% tolerance, same session) appears in this
   turn's actual tool-call results. Three outcomes per claim:
   - **Verified** — matches a real tool response this turn/session.
   - **Stale** — matches a real tool response, but from an earlier day/turn
     (this is a "belief," not a "fact," per `01`'s fact-vs-belief line —
     surfacing this distinction, not just verified/failed, is part of the
     point).
   - **Fail** — no matching tool response anywhere in session history. This
     is the JNJ case. Block or flag before the message is persisted/
     returned — exact enforcement behavior (hard block vs. flag-and-log) is
     an open decision, default to flag-and-log first so this doesn't
     silently break every response before its false-positive rate is
     known against real sessions.
3. **Plug-in point**: `AgentLoop.run()`, after the final assistant message
   is composed, before it's persisted to session history or returned —
   same place noted in `AGENTS.md`'s "don't re-derive" section.

## Files touched

- `vinu-agent/vinu_agent/audit/fact_audit.py` — new: FactAuditor with regex extract → Verified/Stale/Fail verdict against tool-results in session history
- `vinu-agent/vinu_agent/audit/__init__.py` — new: package init, exports FactAuditor
- `vinu-agent/vinu_agent/agent/loop.py` — `_build_result` runs FactAuditor on final answers (completed/max_iterations), stores findings in `result["audit"]`; `_session_id` stored in `run()`

## Bugs and fixes

_None yet. When implementing, log entries here the same way `02-the-1-
month-back-testing/testing-status/*/test-log.md` did: symptom, date,
reproduction, root cause, fix, verification, status. Do not defer this to
a separate file — this file is the combined design + build log per the
convention set in `AGENTS.md`._
