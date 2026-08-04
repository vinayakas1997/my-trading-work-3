---
name: question-entity-mapping-and-freshness
status: definition-phase
purpose: maps the 8 daily-ritual questions (01-vinu-questions-prompt.md) to the 11 knowledge entities (02-knowledge-library-entities.md), classifies each entity by temporal bucket (one-time fact / continuously recorded / periodic reanalysis), and folds in the two structural mechanisms needed to make that classification real instead of another document — a Facts & Limitations Registry and a Freshness Contract. Last planning file before implementation starts.
---

# Question × Entity Mapping, Temporal Buckets, and the Two Structural Mechanisms

## 1. The mapping — which entities feed which question

| # | Question | Entities it draws on | Notes |
|---|---|---|---|
| 1 | Which tickers to focus on today | #4 (derived analytics), #10 (external benchmark/regime context) | Blocked on the signal-usage contract inside #4 — a ticker can't be ranked "focus today" off a signal not proven to support that ranking |
| 2 | What is the risk management | #1 (self-state), #6 (risk mandate/tiers) | Already real (`TradingMandate`) — this question surfaces current state, doesn't compute anything new |
| 3 | History/knowledge of this ticker | #6 (decision journal), #3 (news archive) | Needs the journal (item 3 of `01-plan-and-implementations`) to exist; without it this is narrative recall, the exact failure already found |
| 4 | Performance in last live trades | #6 (journal's predicted-vs-actual), #8 (execution quality) | Same journal dependency as Q3 |
| 5 | What should the plan be | #6 (trade-plan generation), #4 (derived analytics feeding the plan) | Already real but dormant (`generate_trade_plan`) — question's job is forcing the call, not new logic |
| 6 | Which strategy today | #4's signal-usage contract, #5 (what's proven/disproven) | The least-covered question — needs both the contract and the permanent-facts registry (§3 below) to answer honestly |
| 7 | Inconsistencies between market-prep and (history + known knowledge) | #2/#3 (fresh data), #6 (journal), #5 (permanent facts) | This is item 1's audit pattern run prospectively, checking fresh data against the journal *and* the facts registry, not just against itself |
| 8 | Risk / how to behave in this situation | #1 (self-state), #6 (mandate), #9 (self-known limitations), #11 (escalation) | Quantifiable half is mechanical; qualitative half (escalation) stays the confirmed-unsolved gap |

Reading the table: questions 3, 4, 6, 7 are all blocked on things that don't
exist yet (the journal, the signal-usage contract, the facts registry).
Questions 2 and 5 are the only two answerable today, because they're the
only two entities already real in the codebase.

## 2. Temporal classification, per entity

| Entity | Bucket | Why |
|---|---|---|
| #1 Self-state | Continuously recorded | Changes with every fill; must never be stale (per `01-quant-agent-qualities.md`'s hard rule) |
| #2 Live market reality | Continuously recorded (mostly) — **except options greeks/IV, which has zero historical depth anywhere in this stack** | Confirmed limit, not an oversight — any "reanalyze the past" exercise must know this boundary explicitly |
| #3 News & information | Continuously recorded | Archived as it arrives, read fresh |
| #4 Derived analytics (significance/regime/correlation) | Periodic reanalysis | Regime today isn't regime a month ago — genuinely goes stale |
| #5 Research/backtest + permanent facts | One-time / permanent | "Direction prediction doesn't work" doesn't need re-testing on a cadence — it needs to never be silently forgotten |
| #6 Strategy & decision knowledge | Continuously recorded | The journal accumulates, doesn't get "recomputed" |
| #7 Simulation/what-if | Periodic reanalysis | Stress scenarios should refresh as the book and market conditions change |
| #8 Live-trading awareness | Continuously recorded | Execution quality is observed per-fill, not recomputed |
| #9 Self-known limitations (own bug history) | One-time / permanent, until superseded | A fixed bug's entry updates once (fixed); an open bug's entry persists until it's actually closed |
| #10 External benchmark/context | Periodic reanalysis | Same staleness profile as #4 |
| #11 Human/operator context | Continuously recorded (rarely changes, but must never be assumed stale) | Mandate/escalation settings — read fresh, not cached indefinitely |

## 3. Structural mechanism 1 — the Facts & Limitations Registry

Solves: where entity #5's permanent facts and #9's self-known limitations
actually live so the agent can read them at runtime, instead of only
existing as markdown in this planning repo that a human happens to read.

- **Shape**: structured rows, not prose —
  `{id, statement, kind: "proven"|"disproven"|"known-bug",
  applies_to: {signals: [...], symbols: [...]}, evidence_ref, status:
  "active"|"superseded", established_date}`.
- **Seeding**: a one-time migration of what's already proven in this repo
  — "direction prediction from sentiment/FinBERT doesn't work" (`kind:
  disproven`), each replay bug (tool-call dropout, frozen mark-to-market,
  the JNJ fabrication — `kind: known-bug`) — not new research, just giving
  existing findings a machine-readable form.
- **Write side**: whichever component establishes the fact
  (`vinu-initial-analysis`/`vinu-research` when a validation test
  concludes) writes the row.
- **Read side**: `vinu-agent` force-injects a "Known Constraints" block
  into context at session start, filtered to whatever symbols/signals are
  in play that session — same structural, non-optional injection pattern
  as item 2 (forced ground-truth injection) in `01-plan-and-
  implementations/02-forced-ground-truth-injection.md`. Not something the
  agent has to remember to search for.

## 4. Structural mechanism 2 — the Freshness Contract

Solves: who actually triggers re-analysis for anything in the "periodic"
bucket (#4, #7, #10) — must not be agent discretion, or it's the same
"does the agent remember to check" failure relocated to a new kind of
data.

- Every periodic entity declares two properties: a **staleness threshold**
  (e.g. regime data older than 24h is stale) and a **trigger** — either a
  scheduled recompute job (a cron hitting `vinu-initial-analysis`'s
  existing `/analysis/run/...` route on a cadence), or a pull-if-stale
  check performed by item 2's injector at read time.
- If the injector finds a value past its threshold, it either forces a
  recompute call or explicitly labels the injected value `STALE — not
  refreshed since X` rather than presenting it with the same confidence as
  a fresh value — directly implementing `01-quant-agent-qualities.md`'s
  "hard line between fact and belief," applied to derived analytics, not
  just prices.
- Which of the two trigger mechanisms (cron vs. pull-if-stale) is used per
  entity is an implementation decision for whoever builds item 2 /
  whichever item ends up owning this — not decided in this file, but the
  *contract* (threshold + trigger, no silent staleness) is fixed here.

## 5. Three design decisions, made independent of the codebase — resolve these before checking `vinu-components`, not after

These settle the shape of the two structural mechanisms above before any
code is read, so the codebase check verifies a real plan instead of
improvising one on contact.

### Decision 1 — one seam, multiple independent providers, shipped one at a time

The pre-reasoning context-assembly point (wherever it physically lives)
must be built as a generic seam that accepts pluggable blocks, not one
monolithic feature. Ground-truth prices (item 2's original scope), the
Facts & Limitations Registry (§3), and staleness-labeling (§4) are three
separate providers registered against the same seam — each independently
buildable, independently verifiable, independently revertible. Build the
seam once; ship the ground-truth-for-held-positions provider first (it has
direct replay evidence behind it), then the Facts Registry provider, then
staleness-labeling — without re-touching the seam's core logic each time.
Not three risky touches to the same file, and not one oversized feature.

### Decision 2 — the recompute and the staleness-check are two separate responsibilities, never one component

Whatever recomputes regime/correlation on a cadence (§4's periodic bucket)
must be an out-of-band, timer-driven job — it runs on its own schedule,
writes fresh values to storage, with zero awareness of whether any agent
session happens to be running that day. The agent-side reader (the
provider from Decision 1) is only ever a **reader**: it checks a value's
timestamp against its declared threshold and either trusts it or labels it
`STALE`. It must never be the thing that *triggers* the recompute — the
moment the agent-side becomes responsible for "go refresh this,"
discretion has crept back in under a new name. True regardless of whether
a scheduler already exists anywhere in `vinu-components` — if it doesn't,
building one is the actual task; the computes-vs-reads boundary doesn't
move either way.

### Decision 3 — the audit and the model/token-budget lever must never depend on each other

Item 1 (fact-verification audit, `01-plan-and-implementations/01-fact-
verification-audit.md`) ships as a hard, unconditional layer regardless of
model or token budget — its design must assume fabrication *can always
happen*, never "the model won't fabricate because the budget got tuned."
Separately, raising `max_tokens` or reconsidering model capability (the
Bug-5 root-cause hypothesis from the replay) is a cheap, orthogonal
deployment lever that lowers how *often* item 1 has to catch something —
real, worth doing, but a tuning decision, not a prerequisite. Ship item 1
as if the token-budget fix will never happen; treat the token-budget fix
as a bonus on top, not a dependency underneath.

### Decision 4 — one relational store, no vector database; scheduler is a separate, real open question

Going through every entity that needs storage — self-state, the Facts &
Limitations Registry, the decision journal, the audit log — all of them
are small, structured, exact-match/filter-by-symbol lookups (facts for
AAPL, open journal entries, audit events for this session). That's
relational data; none of it needs semantic similarity search. The one
place a vector DB could plausibly help is the news archive (#3) — "find
past events similar in character to this one" — but none of the 8
questions actually ask for that; they ask for time-filtered/ticker-filtered
retrieval, which keyword/full-text search already covers (`vinu-agent`'s
existing FTS-based `UnifiedMemoryStore` already does this). **Decision: no
vector database is needed anywhere in this plan** — introducing one would
solve a retrieval problem none of the 8 questions or 11 entities actually
have. Self-state, facts registry, journal, and audit log are four tables
(or four small stores) in one relational shape, not four different
technologies.

The **scheduler is a separate, genuinely open question**, not a storage
question. Decision 2 requires something that runs on a timer, independent
of whether an agent session is active, to recompute regime/correlation on
a cadence. Whether any such mechanism already exists anywhere in
`vinu-components` is unknown and unresolved until the codebase is actually
checked — this is real new architecture if it doesn't exist, not a
database choice.

## 6. What this file deliberately does not do

Does not decide file paths inside `vinu-components` for either mechanism —
that's the component-ownership mapping flagged as the next step after this
one, not done here. Does not add a 5th item to `03-on-agent-consiuness/01-
plan-and-implementations/` — whether the Facts Registry and Freshness
Contract become their own item files there, or fold into existing items 1-2,
is an open decision to make when implementation actually starts.

## Related documents

- [`01-vinu-questions-prompt.md`](01-vinu-questions-prompt.md) — the 8
  questions this file maps entities onto.
- [`02-knowledge-library-entities.md`](02-knowledge-library-entities.md)
  — the 11 entities this file classifies and maps.
