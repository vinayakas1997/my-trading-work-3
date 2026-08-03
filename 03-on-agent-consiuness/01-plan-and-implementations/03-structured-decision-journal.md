---
name: structured-decision-journal
component: vinu-agent
status: implemented
---

# Item 3 — Structured Decision Journal

## Where to fetch the details

- Reference pattern, read in full: `personal-important/other-reference-
  repos/Vibe-Trading/agent/src/hypotheses/registry.py` (`HypothesisRegistry`
  — JSON-backed, real status lifecycle `exploring → testing → validated →
  rejected → monitoring`, `invalidation_notes` field) and `agent/src/
  skills/thesis-tracker/SKILL.md` (per-holding thesis file with a
  5-sentence core thesis, falsifiable assumptions table, explicit
  red-lines, quarterly re-check producing a 1-10 health score + hold/add/
  trim/exit verdict). Summarized in `../03-advanced-patterns-from-
  reference-repos.md` §"Structured decision journal, distinct from chat
  history."
- What already exists in `vinu-components` and is relevant:
  `vinu_agent/tools/trade_plan_tool.py`'s `generate_trade_plan` already
  produces real invalidation/exit rules from regime analysis, factors,
  backtest validation, and news sentiment — but the replay confirmed it was
  never called during the 20-day run, and even when it is called, nothing
  persists its output anywhere structured. `vinu_agent/memory/
  unified_store.py`'s `UnifiedMemoryStore` is freeform FTS-searchable text,
  symbol-tagged but not a structured predicted-vs-actual record.
- Codebase gap this fixes: `../02-vinu-components-where-how.md`'s
  "structured decision/outcome journal" row (tagged ❌ entirely missing,
  → see 03).

## Why

`vinu-agent` has no queryable record of what it decided, why, what it
predicted, and what actually happened. `01-quant-agent-qualities.md`'s
"data" layer is explicit that without this, the agent can only pattern-
match on the tone of its last few paragraphs — which is not the same thing
as updating a belief. The replay's own re-issued, barely-changing daily
paragraphs are exactly what that failure mode looks like in practice.

## Impact

Gives `generate_trade_plan`'s already-real invalidation rules somewhere
persistent to live, instead of being generated once and then discarded.
Closes the predicted-vs-actual loop `01` calls the actual learning
mechanism — without this, any future "did the agent learn from being
wrong" question (like the replay's Section 3 questions, which this project
could only partially answer) stays permanently unanswerable from real
data.

## What decision-dots this connects to for the future

- Depends on item 2 (forced ground-truth injection) being in place first —
  see `AGENTS.md`'s execution order. A journal entry is only meaningful if
  the data behind the original decision was actually fresh.
- Directly enables the "debriefing itself when a position closes" skill
  from `01-quant-agent-qualities.md` §3 — that skill has nowhere to write
  its predicted-vs-actual comparison without this journal existing first.
- Becomes the natural source for a future escalation mechanism to query
  ("has this thesis's invalidation condition already triggered, and the
  agent hasn't acted on it?") — not building that mechanism now, but this
  journal is the data it would need.

## Implementation

- New module, e.g. `vinu_agent/journal/registry.py` — JSON- or SQLite-
  backed (SQLite preferred given `vinu-components`' existing pattern of
  per-service `meta.db` stores; check what's already used for the current
  session store, `vinu_agent/session/service.py`, before picking a new
  storage mechanism).
- One record per open thesis: symbol, entry thesis (falsifiable, per `01`
  §3's "bullish because X, and specifically Y happening would prove this
  wrong" standard — not a vibe), invalidation level/condition, size,
  status (`exploring → testing → validated → rejected → monitoring`,
  mirroring `HypothesisRegistry`'s lifecycle), predicted outcome, actual
  outcome (filled in on close or on invalidation-check).
- **Population point**: `generate_trade_plan`'s output
  (`vinu_agent/tools/trade_plan_tool.py`) should write a new registry entry
  instead of only returning a one-off checklist to the model. This makes
  the plan tool's existing, real invalidation logic actually persist
  somewhere instead of evaporating after one turn.
- **Review point**: as part of item 2's forced-injection ritual, check each
  open registry entry's invalidation condition against the freshly-
  injected ground-truth data every turn a relevant symbol appears —
  surfacing "invalidation condition met" as part of the injected context,
  not something the model has to remember to check.
- Explicitly out of scope for the first pass: a full quarterly health-score
  re-check (`thesis-tracker`'s 1-10 score) — start with the simpler
  status-lifecycle + invalidation-check, add scoring later if the simpler
  version proves useful.

## Files touched

- `vinu-agent/vinu_agent/tools/trade_plan_tool.py` — `_schedule_journal_write` + `_write_trade_journal_async`: after generating a plan, creates a trade-thesis hypothesis entry in vinu-research's HypothesisRegistry via POST /hypotheses with structured plan data (direction, entry rules, exit rules)
- `vinu-agent/vinu_agent/audit/ground_truth.py` — `_fetch_open_theses` queries GET /hypotheses for open (testing/exploring/monitoring) theses per held symbol; theses are included in the `<ground-truth>` block so invalidation conditions are visible every session

## Bugs and fixes

_None yet. Log entries here as they're found during implementation —
symptom, date, reproduction, root cause, fix, verification, status._
