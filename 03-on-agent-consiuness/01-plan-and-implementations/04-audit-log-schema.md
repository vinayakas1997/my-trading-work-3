---
name: audit-log-schema
component: vinu-agent
status: implemented
---

# Item 4 — Audit-Log Event Schema

## Where to fetch the details

- Reference pattern, read in full: `personal-important/other-reference-
  repos/ref-fincept-terminal`'s `AuditLogger` — `AuditEntry{id, action,
  workflow_id, node_id, symbol, details, metadata(JSON), paper_trading,
  timestamp}`, action enum covering `RiskCheckPassed/Failed,
  ConfirmationApproved/Rejected, OrderPlaced/Filled`. Summarized in
  `../03-advanced-patterns-from-reference-repos.md` §"ref-fincept-
  terminal — a cautionary confirmation, plus one reusable schema."
- The cautionary half of this same repo, worth re-reading before starting:
  `RiskManager::validate_order()`/`is_order_allowed()` and
  `ConfirmationService` are both complete, well-designed gates — grepping
  the entire repo for callers outside their own class returns **zero
  results**. Built, never wired into the live-order path. This is the
  specific mistake this item's first task exists to rule out in
  `vinu-components`.
- What already exists and works in `vinu-components`:
  `vinu_agent/broker/mandate.py`'s `TradingMandate`/`OrderGuard` — per `03`,
  confirmed to be the one governor genuinely in the live order call path,
  not just present in the codebase. Good news, but confirm it again by grep
  before assuming it still holds, since codebases drift.
- Codebase gap this fixes: no existing "what happened, when" event trail
  distinct from the freeform session/chat history.

## Why

Cheap and mechanical relative to items 1-3, but it closes a real gap: right
now there's no way to answer "did the risk check actually run on this
order" or "was this confirmation ever requested" except by re-reading raw
session transcripts. `ref-fincept-terminal` shows exactly what goes wrong
when a project skips this and just assumes its gates are wired in — they
weren't, and nothing surfaced that until someone grepped for it.

## Impact

Gives items 1-3 (and the existing `TradingMandate`) a shared, queryable
event trail underneath them, instead of each one inventing its own ad hoc
logging. Makes "is X actually enforced" a fact you can query, not an
assumption you carry forward — directly useful the next time this project
needs to re-verify a governor is still in the call path after refactoring.

## What decision-dots this connects to for the future

- Item 1's audit verdicts (`Verified`/`Stale`/`Fail`) and item 3's journal
  status transitions should both log into this same event trail rather
  than maintaining separate logs — one place to look for "what happened,"
  consistent with `01-quant-agent-qualities.md`'s "provenance and
  timestamp metadata on every piece of data" principle.
- The first concrete task under this item (re-confirm `TradingMandate`/
  `OrderGuard` is still genuinely wired into the live order path, via grep,
  not assumption) has no dependency on items 1-3 and can be done any time
  — it's a cheap sanity check worth doing early, independent of whether
  the rest of this item is built yet.

## Implementation

- Reuse the schema shape as-is: `{id, action, session_id, symbol, details,
  metadata (JSON), paper_trading, timestamp}` — `session_id` in place of
  `workflow_id`/`node_id` since `vinu-agent` doesn't have fincept's
  workflow-node concept.
- Action enum, extended for what items 1-3 introduce beyond fincept's
  original set: `RiskCheckPassed`, `RiskCheckFailed`, `OrderPlaced`,
  `OrderFilled`, plus new ones — `GroundTruthInjected` (item 2),
  `AuditVerdictFail` / `AuditVerdictStale` (item 1),
  `JournalEntryCreated` / `JournalStatusChanged` (item 3).
- Single append-only store — check what storage `vinu-agent` already uses
  per-service (SQLite `meta.db` pattern seen elsewhere in this repo) before
  introducing a new mechanism; a small shared helper module (e.g.
  `vinu_agent/audit/log.py`) called from `broker/mandate.py`, the new
  fact-audit hook (item 1), and the new grounding injector (item 2).
- **First task, before writing any new logging code**: grep
  `vinu_agent/broker/mandate.py`'s `TradingMandate`/`OrderGuard` for actual
  callers in the live order path (`trade_tool.py`, `broker/alpaca.py`), and
  record the result here under "Bugs and fixes" even if the answer is
  "confirmed still wired in, no bug" — the point is doing the check
  explicitly, not assuming the earlier `03` finding still holds.

## Files touched

- `vinu-agent/vinu_agent/broker/kill_switch.py` — `AuditLogger.log()` extended with fixed schema fields (`id`, `session_id`, `symbol`, `details`, `metadata`, `paper_trading`, `timestamp`) and new action constants: `RiskCheckPassed`, `RiskCheckFailed`, `OrderPlaced`, `OrderFilled`, `GroundTruthInjected`, `AuditVerdictFail`, `AuditVerdictStale`, `JournalEntryCreated`, `JournalStatusChanged`
- `vinu-agent/vinu_agent/audit/ground_truth.py` — logs `GroundTruthInjected` on each successful injection
- `vinu-agent/vinu_agent/audit/fact_audit.py` — logs `AuditVerdictFail`/`AuditVerdictStale` on fact-audit failures
- `vinu-agent/vinu_agent/tools/trade_plan_tool.py` — logs `JournalEntryCreated` on trade-plan journal write
- `vinu-agent/vinu_agent/tools/trade_tool.py` — existing `order_rejected`/`order_pending_confirmation`/`order_executing`/`order_error` calls updated to pass `symbol`/`details` via the new signature (backward-compatible)

## Bugs and fixes

- 2026-08-03 — **Re-confirmed**: `OrderGuard.check()` is genuinely called in the live order path at `trade_tool.py:137,141`. No bug. The earlier `03` finding still holds — `TradingMandate`/`OrderGuard` is the one governor confirmed wired in.

## Bugs and fixes

_None yet. Log entries here as they're found during implementation —
symptom, date, reproduction, root cause, fix, verification, status. The
`TradingMandate` re-confirmation grep described above should be the first
entry, whatever its result.
