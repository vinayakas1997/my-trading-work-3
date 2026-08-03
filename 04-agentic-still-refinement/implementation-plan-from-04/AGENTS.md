---
name: agents
status: implemented
purpose: single source of truth for the remaining work identified in 04-agentic-still-refinement (Facts & Limitations Registry, Freshness Contract, signal-usage contract), organized by which vinu-* component owns each piece. All three components' work is now implemented and tested. Companion to 03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md, which already shipped items 1-4.
---

# Implementation Plan From 04 — Component-Wise

## Scope — closed, not open for re-debate

**Exactly three components have real work in this plan: `vinu-agent`,
`vinu-initial-analysis`, `vinu-research`.** This is decided, stated once,
here — not re-opened in future discussion. The 11-entity knowledge library
(`../02-knowledge-library-entities.md`) named two things that touch other
components — entity #7 (simulation/what-if, `vinu-simulator`) and entity
#10 (external benchmark context, `vinu-portfolio`/`vinu-stock-price`) —
but neither was ever turned into a scoped build item; they were named
during brainstorming, not scoped as work. **Out of scope for this round,
final.** No folder exists for them, and none should be added without a
new, explicit decision to promote one of them to a real item first.

## Scope addendum — checked against all four `04-` files, three findings, all closed now

Going back through `01-vinu-questions-prompt.md`, `02-knowledge-library-
entities.md`, and `03-question-entity-mapping-and-freshness.md` against
this plan found three things not yet assigned anywhere. All three are
closed now, not left open:

- **Question 1's watchlist/ranking ("which tickers to focus on today")**
  — **explicitly punted**, same as entities #7/#10. Not needed for any of
  the 4 already-shipped items or the 3 items below to function; a
  "nice-to-have" ranking layer, not a discipline fix. No folder, no plan
  file, not revisited without a new explicit decision to promote it.
- **Question 4's debrief-on-close (predicted-vs-actual on position
  close)** — **added to `vinu-agent/plan.md`**. Item 3 shipped the write
  side (thesis in); this is the missing read-back side that actually
  closes the learning loop.
- **Question 7's prospective fact-check** — **added to `vinu-agent/
  plan.md`**. Item 1 shipped as a post-hoc check only; this extends
  `FactAuditor` to run before a plan is committed to, not only after an
  answer is composed.

## What's already done — don't rebuild this

`03-on-agent-consiuness/01-plan-and-implementations/` (items 1-4) already
shipped: forced ground-truth injection, fact-verification audit, the
decision journal (reusing `vinu-research`'s `HypothesisRegistry`), and the
audit-log schema (extending `vinu_agent/broker/kill_switch.py`'s existing
`AuditLogger`). 224 tests passing. This plan is what's left **after**
that — the Facts & Limitations Registry and Freshness Contract from
`../03-question-entity-mapping-and-freshness.md`, plus the signal-usage
contract from `../01-vinu-questions-prompt.md` question 6. Do not
re-derive or re-propose anything items 1-4 already closed.

## The three components — one-line summary, full detail in each folder

| Component | What it owns here | Status |
|---|---|---|
| [`vinu-agent/`](vinu-agent/plan.md) | The Facts & Limitations Registry, debrief-on-close, prospective fact-check, freshness-warnings reader, research-digest reader | All 5 pieces implemented (280 tests passing; +3 real pre-existing bugs found and fixed along the way) |
| [`vinu-initial-analysis/`](vinu-initial-analysis/plan.md) | The signal-usage contract (proven-for/not-for tags on `significance_score`/`regime_features`) | Implemented (4 tests passing). Recompute job hosted in `vinu-research` instead — see that row |
| [`vinu-research/`](vinu-research/plan.md) | The daily regime/correlation recompute job, hosted on the existing `ScheduledResearchExecutor` (decided over a new executor in `vinu-initial-analysis`) | Implemented (4 new tests; 489 passed project-wide, 1 pre-existing unrelated failure) |

Each folder has `plan.md` (what, why, impact, connects-to, implementation)
and `status.md` (files touched, bugs/fixes, filled in during build) — a
deliberate two-file split for this folder, different from the single
combined file used per item in `01-plan-and-implementations/`, because
here it's one component with potentially several things landing in it,
not one mechanism with one file.

## Execution order

1. **`vinu-initial-analysis`'s signal-usage contract first** — smallest,
   most self-contained (tagging existing angle output), and the Facts
   Registry (`vinu-agent`) needs somewhere real to source its "proven/
   disproven" rows from — this is one of those sources.
2. **`vinu-agent`'s Facts & Limitations Registry** — depends on #1 existing
   to seed from, plus the already-shipped ground-truth seam (item 2) to
   plug its provider into.
3. **`vinu-research`'s scheduler hosting** — last, since it's plumbing for
   the recompute job and has no dependency on the other two being done
   first; could genuinely be done in parallel if useful.

## What to actually focus on while testing — one list, not per-component

Same "bypass the LLM first" discipline items 1-4 already used
(`historical_broker.py`, `options_tool.py` precedent) — direct/unit-level
verification before any real session run, because it's cheaper and
catches more per test:

1. **Facts Registry (`vinu-agent`)**: confirm a seeded row actually appears
   in the injected context block for a matching symbol/signal — not just
   that the row exists in the store. The failure mode to specifically
   test for: a row that exists in the database but never reaches the
   model, which is functionally identical to it not existing at all.
2. **Debrief-on-close (`vinu-agent`)**: confirm the predicted-vs-actual
   write actually happens **on a real position close event**, not just
   that the field exists in the schema. Test the actual trigger path
   (order fill → close detection → registry write), not just that the
   registry *can* store an outcome if told to.
3. **Prospective fact-check (`vinu-agent`)**: the one test that matters
   most — reconstruct the actual JNJ scenario from the replay (a plan
   about to state a price with no matching tool call this session) and
   confirm it's caught **before** the plan is committed to, not after.
   This is the direct, named acceptance test for this specific piece —
   don't consider it done without running exactly this case.
4. **Signal-usage contract (`vinu-initial-analysis`)**: confirmed the tags
   attach to the angle's own stored output rows (`test_signal_contract.py`,
   including through `regime_analysis.compute()`'s real return value). **Not
   built or tested**: an actual cross-service round trip into `vinu-agent`'s
   Facts Registry — `vinu-agent`'s registry is seeded from the hardcoded
   `SEED_FACTS` list, not by reading `vinu-initial-analysis`'s tagged output
   over HTTP. That wiring was never part of either plan.md's implementation
   steps and is a real, currently-open gap if a future fact needs to flow
   from the tag straight into the registry automatically.
5. **Freshness recompute — both halves now implemented**: the recompute
   *trigger* (`vinu-research`'s `regime_recompute_scan()`, `test_scheduled.py`)
   and the reader-side "mark `STALE` if past threshold" half
   (`vinu-agent`'s `FreshnessChecker`, injected via the same `ContextBuilder`
   seam as ground-truth/facts — `test_freshness.py` +
   `test_integration_freshness.py`, 13 tests, including the same
   reaches-the-actual-block acceptance test used for the Facts Registry).
   Live-mode only — skipped in replay, where "now" is a simulated past date
   and a wall-clock age comparison would be meaningless.

**The one thing to explicitly avoid**: re-running the full 20-day replay
to "check" any of this. Per `00-start-here.md` and `03-on-agent-
consiuness`'s own established discipline, that's expensive and each of
the 5 tests above is independently and more cheaply verifiable without it.
A short, targeted replay (a few days, not twenty) is only worth it as a
final combined check after all of the above pass individually.

## Related documents

- [`../01-vinu-questions-prompt.md`](../01-vinu-questions-prompt.md),
  [`../02-knowledge-library-entities.md`](../02-knowledge-library-entities.md),
  [`../03-question-entity-mapping-and-freshness.md`](../03-question-entity-mapping-and-freshness.md),
  [`../04-vinu-components-integration-plan.md`](../04-vinu-components-integration-plan.md)
  — the four planning files this implementation plan is built from.
- [`../../03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md`](../../03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md)
  — the already-shipped items this plan builds on top of.
