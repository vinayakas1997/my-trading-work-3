---
name: vinu-agent-plan
component: vinu-agent
status: implemented
---

# vinu-agent — Facts & Limitations Registry, Debrief-on-Close, Prospective Fact-Check, Freshness Reader, Research-Digest Reader

Five pieces of work land in this component, all implemented. Piece 1 (Facts
Registry) is the original scope of this file; pieces 2 and 3 were added
after checking this plan against all four `04-` files and finding two
things question 4 and question 7 needed that item 3 and item 1 hadn't
actually finished — see `../AGENTS.md`'s "Scope addendum" for why. Piece 4
was added after the `vinu-research` recompute job landed and left the
reader-side half of the Freshness Contract still open. Piece 5 was added
after `end-to-end-test/` found that no research run's outcome was ever
summarized in plain language or surfaced to anyone.

## Piece 1 — Facts & Limitations Registry

### What the plan is

A new, small SQLite-backed store — `{id, statement, kind: "proven"|
"disproven"|"known-bug", applies_to: {signals, symbols}, evidence_ref,
status: "active"|"superseded", established_date}` — plus a new provider on
`ContextBuilder`'s existing block-injection seam that force-surfaces the
active rows relevant to a session's symbols/signals, the same
non-optional way item 2's ground-truth block already works.

### Why

Two categories of hard-won knowledge currently exist only as markdown in
this planning repo, unreadable by the agent at runtime: **permanent
facts** ("direction prediction from sentiment/FinBERT doesn't work,
tested twice, ~50% coin-flip" — `01-the-stage-2-claude/full-plan.md:68-
74`) and **this project's own documented failure modes** (the tool-call
dropout, the frozen mark-to-market bug, the JNJ fabrication). Without a
machine-readable form, a future agent instance — or this same agent much
later — could silently "rediscover" a disproven approach and start relying
on it again, or repeat a mistake this project already caught and fixed
once.

### Impact

Closes the concrete gap flagged in
`../../03-question-entity-mapping-and-freshness.md` §3: knowledge that
currently only a human reading this repo would know, now reaches the
agent's actual context the same structural way item 2's prices do. Small
in code size, large in what it prevents — a second occurrence of a
mistake this project has already paid to learn from once.

### What decision-dots this connects to for the future

- Sourced partly from `vinu-initial-analysis`'s signal-usage contract
  (`../vinu-initial-analysis/plan.md`) — that's where "proven for X, not
  for Y" tags on `significance_score`/`regime_features` originate; this
  registry is one of (at least) two writers, not the sole owner of all
  fact rows.
- Shares its log format with the already-shipped `AuditLogger`
  (`vinu_agent/broker/kill_switch.py`) rather than inventing a separate
  one — any write to this registry should log through the existing
  action-constant pattern items 1-4 already established.
- Becomes the natural data source a future escalation/confidence mechanism
  would query — not built here, but this registry is what it would read
  from when it eventually is.

### Implementation

- New module, e.g. `vinu_agent/facts/registry.py`, following the same
  `SQLiteBackend` subclass pattern already used by `UnifiedMemoryStore`
  (`vinu_agent/memory/unified_store.py`) — own `.db` file under
  `data/agent/`, or a new table in an existing one; implementation-time
  call.
- **Seed data, not new research**: migrate what's already proven in this
  repo — the direction-prediction finding (`kind: disproven`), each
  replay bug (`kind: known-bug`) — as the first rows. This is a one-time
  data-entry task, not a research task.
- **Write side, going forward**: whichever component establishes a new
  fact writes a row — initially just `vinu-initial-analysis` via the
  signal-usage contract; manual seeding covers everything else for now.
- **Read side**: register a new provider on `ContextBuilder.build_messages()`
  (`vinu_agent/agent/context.py`) — same seam item 2's `GroundTruthInjector`
  already uses — filtered to whatever symbols/signals are in play that
  session, injected as a "Known Constraints" block.

## Piece 2 — Debrief-on-close (predicted-vs-actual)

### Why

Item 3 shipped the write side of the journal — `trade_plan_tool.py`'s
`_schedule_journal_write` records a thesis into `HypothesisRegistry` at
`status: testing` when a plan is generated. Nothing confirmed writes the
outcome back when the position actually closes. A journal that only ever
receives entries and never receives their resolution is a log, not the
learning mechanism `01-quant-agent-qualities.md` names as the actual point
of having a journal at all — "debriefing itself when a position closes...
explicitly comparing what it predicted to what happened."

### Impact

This is the step that makes the whole journal worth having. Without it,
every thesis sits at `status: testing` forever, or gets manually closed
with no record of whether the original invalidation/target logic was
right — the exact "did it learn from being wrong" question this project
could not answer from the 1-month replay stays unanswerable going forward
too, even after items 1-3 shipped.

### Implementation

- Hook into wherever a position close is actually detected — the broker's
  fill/order-close path (`vinu_agent/broker/`), not a new polling
  mechanism.
- On close, look up the open `HypothesisRegistry` entry for that symbol
  (`status: testing`) and write the actual outcome (realized P&L, whether
  the invalidation condition was the reason for exit or something else)
  using the registry's existing evidence/status-update mechanism
  (`add_hypothesis_evidence`-style call, per the other agent's summary of
  what already exists) — transition status to whatever the registry's
  lifecycle calls "resolved," not leave it at `testing`.
- Log the write through the existing `AuditLogger`
  (`JournalStatusChanged` action, already defined per item 4).

## Piece 3 — Prospective fact-check

### Why

`01-fact-verification-audit.md` said this extension should happen "when
picked up for implementation." It shipped as post-hoc only — `FactAuditor`
runs from `AgentLoop._build_result`, after the final answer is already
composed. Question 7 (`../../01-vinu-questions-prompt.md`) asks for the
same check run **before** a plan is committed to — catching a fabricated
number at the point it would have been acted on, not just at the point
it's already been said.

### Impact

This is the more direct fix for the actual JNJ failure than the post-hoc
version alone — the post-hoc audit still lets a fabricated number
influence a same-turn trading decision before anything flags it; a
prospective check catches it before the decision is made on top of it.

### Implementation

- Reuse `FactAuditor` (`vinu_agent/audit/fact_audit.py`) — same extract →
  verdict logic — but call it a second time, earlier: after
  `generate_trade_plan` produces a structured plan but before that plan is
  acted on (order submitted) or written into the journal (Piece 2 /
  item 3).
- **Acceptance test, not optional**: reconstruct the actual replay
  scenario — a plan about to state JNJ at a price with no matching tool
  call this session — and confirm this catches it before the plan is
  committed. This is the named test in `../AGENTS.md`'s testing-focus
  section; don't consider this piece done without running exactly this
  case.

## Piece 4 — Freshness-warnings reader

### Why

The Freshness Contract (`../../03-question-entity-mapping-and-freshness.md`
§4) has two halves: a recompute *trigger* (built in `vinu-research`'s
`regime_recompute_scan()`) and a reader that checks a value's age at the
point it's about to be used and labels it `STALE` past a threshold. A
working recompute job doesn't help if nothing ever checks whether it
actually ran on time for a given symbol — this piece is that check.

### Impact

Closes the reader-side gap flagged after Piece 3/the `vinu-research` work
landed: without it, a symbol whose recompute job silently failed (network
blip, service down, symbol dropped from the universe) would look identical
to one that's perfectly fresh — the agent has no way to tell the difference
between "checked recently" and "haven't checked in a week."

### Implementation

- New `vinu_agent/audit/freshness.py` — `FreshnessChecker`: for each symbol
  in play, `GET`s `vinu-initial-analysis`'s existing
  `/analysis/angle/regime_analysis/{symbol}` route, reads the `analysis_at`
  timestamp every row already stamps on write, and flags the symbol if the
  latest one is older than `STALE_AFTER_DAYS` (2.0 — daily recompute + 1 day
  slack). No new field needed on the `vinu-initial-analysis` side.
- Wired into `ContextBuilder`'s existing block-injection seam (same pattern
  as `GroundTruthInjector`/`FactsRegistry`) as a `<freshness-warnings>`
  block, preserved across `_auto_compact()` the same way.
- **Live-mode only**: `session/service.py` only constructs a
  `FreshnessChecker` when `as_of is None` — comparing a timestamp to
  wall-clock `now()` is meaningless in replay, where "now" is a simulated
  past date.

## Piece 5 — Research-digest reader (how the user/agent finds out what happened)

### Why

Found while writing `end-to-end-test/`: `vinu-research`'s `run_research()`
produced a `report_md` field, but it's a metrics table, not an explanation
— and nothing ever pushed it anywhere. `ScheduledResearchExecutor.dispatch()`
called `run_research()` and **discarded the return value entirely**; the
agent only learned about a run if it happened to ask. A working strategy-
generation pipeline is worthless if nobody — human or agent — ever
naturally learns what it did.

### Impact

Closes the "how does the user get a summary of what happened" gap
end-to-end: `vinu-research` now generates a genuine plain-English narrative
per run (not a repeat of the metrics table), persists it durably even for
scheduled/cron-triggered runs, and `vinu-agent` proactively surfaces the
most recent *unseen* run per symbol the next time that symbol comes up in
a session — the same "next natural touchpoint" pattern every other piece
in this project uses, since there's no push channel to a human outside a
session.

### Implementation

- **`vinu-research` side**: `ResearchRunRecord` gained `summary_text: str`
  (`storage/models.py`, `storage/sqlite_backend.py` — schema v3→v4,
  migration added). `ResearchLlmClient.summarize_run()` (`llm.py`) makes
  one best-effort LLM call (gated on `config.llm_enabled`, same pattern as
  `refresh_strategy`'s LLM use) after a run's metrics are known, returning
  2-4 plain-English sentences — empty string if the LLM isn't configured or
  the call fails, never raises. `run_research()` (`service.py`) calls it
  and persists the result; `summary_text` is now in every `run_research()`
  response and every `GET /research/runs`/`GET /research/runs/{id}` row (no
  new route needed, `to_dict()` already serializes it).
- **The `dispatch()` discard, fixed**: `ScheduledResearchJob` gained
  `last_run_id`/`last_summary` (`scheduled/models.py`); `dispatch()`
  (`scheduled/executor.py`) now persists both from `run_research()`'s
  return value instead of throwing it away.
- **`vinu-agent` side**: new `vinu_agent/audit/research_digest.py` —
  `ResearchDigestReader`: for each symbol in play, `GET`s
  `/research/runs?symbol={s}&limit=1` (already ordered by recency, no new
  route needed there either), and surfaces it only if its run `id` hasn't
  already been shown for that symbol — tracked in a small persisted state
  file, the same "seen" mechanic as `PositionCloseDetector`'s snapshot
  file. Wired into `ContextBuilder`'s seam as a `<recent-research>` block,
  preserved across `_auto_compact()` the same way as the other three.
  Runs in both live and replay mode (unlike Piece 4 — a run either happened
  or didn't, no wall-clock dependency).

## Files touched, bugs, and fixes

Tracked in [`status.md`](status.md), not here — this folder uses the
two-file split (this file is design-only; the build log lives separately).
Log entries per-piece (Piece 1 / Piece 2 / Piece 3 / Piece 4 / Piece 5) so
it's clear which part of this file each status update belongs to.
