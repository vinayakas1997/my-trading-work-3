---
name: vinu-agent-data-architecture-9-pillars
status: proposed-not-built
purpose: the 9 pillars the shared data/storage architecture for vinu-agent's new teams needs to cover, before any of the 6 proposed teams (strategist, strategy_lab, risk_gatekeeper, capital_allocator, trade_monitor, post_trade_review) can be built for real -- every one of them is currently blocked on some part of this.
---

# vinu-agent data architecture — 9 pillars

Why this comes before building any new team: writing out the full
per-team prompts in
[../agents-explanation-in-detail/](../agents-explanation-in-detail/)
surfaced that 6 of the 8 teams are blocked on shared data that doesn't
exist yet — `strategist`'s spec schema, the per-symbol memory ledger, the
shadow ledger, `get_portfolio_exposure`, `compute_allocation_candidates`.
Building those teams' `TEAM.md`/`AGENT.md` files now would mean writing
specialists that call tools pointing at nothing. This doc is the map of
what has to be decided first, and why each piece matters — not the final
answer to any of them yet.

The agent *mechanism* itself doesn't need more work here — `screener` and
`research` already prove manager+specialist delegation, logging, and
run-tracking work end to end against a real LLM. Everything below is
about the data those (and the 6 proposed) teams read and write, not about
how agents talk to each other.

## 1. API design — how anyone queries previous results

Every team that reads a prior result (a strategy spec, a memory-ledger
entry, a shadow-ledger snapshot, a past run) needs a clear, consistent way
to fetch it — and to update it, where updates are even allowed (see
pillar 6). This needs to answer, for each object type: how do you fetch
the latest one, how do you fetch a specific historical one, how do you
list/filter by symbol or time range, and what does an update step
actually look like when one is needed (e.g. a memory-ledger entry's
status changing from `exploring` to `validated`).

**Not starting from zero:** this project already has a real, decided
pattern for exactly this question — `AngleStorage`'s "latest" is always
resolved through a SQL run log, **never filesystem mtime** (a bug that
pattern exists specifically to prevent, per the real storage design doc).
Whatever API shape gets chosen for the new stores should follow that same
discipline rather than reinventing it.

## 2. Uniqueness — stable identity per object, and dedup

Every object needs a real, stable ID: a strategy spec, a `team_runs` row,
a position, a memory-ledger entry. Two sub-questions worth being explicit
about:

- **What's the ID, and who assigns it?** (UUID at creation time, same
  pattern `team_runs`/`team_tasks` already use.)
- **Dedup** — if the same strategist call comes in twice for the same
  symbol in a short window, should it produce two specs or reuse a recent
  one? This isn't new to this design — the original architecture doc
  already flagged `vinu-tools`'s `request_hash` pattern as a real, open
  question ("if the same research question comes in twice, reuse a recent
  PASS instead of re-running the whole team?") — still not decided, and
  now relevant to more teams than just `research`.

## 3. Storage for responses and run details — "the harness"

The operational bookkeeping layer: what actually ran, what it returned,
how long it took, what it cost. Two pieces of this are **already built
and real** — `team_runs`/`team_tasks` (one row per delegation, status
pending/running/completed/failed) and `llm_calls` (full prompt, response,
tokens, latency, tagged by tier/team/agent/role, on every single LLM
call anywhere in the system). What's still missing is the equivalent for
the *new* objects these teams produce: a `strategy_specs` store, the
memory ledger, the shadow ledger, a position/exposure snapshot store —
same discipline, same `SQLiteBackend` pattern already used for the two
built ones, just not built yet for these.

## 4. External access vs. internal access

Two genuinely different kinds of data flow, worth keeping structurally
separate:

- **External** — pulling data FROM other services: angle data from
  vinu-initial-analysis, feature/price/fundamentals data from vinu-tools,
  backtest results from vinu-simulator, real position/order data from
  wherever the broker layer ends up living. vinu-agent doesn't own this
  data, only reads it (mostly read-only, via the existing tool pattern —
  `get_all_angles`, `get_features`, `run_backtest` already work this way).
- **Internal** — vinu-agent's own stores: `team_runs`, `llm_calls`, and
  the new ones from pillar 3. vinu-agent owns these outright, reads and
  writes them.

## 5. Schema / shape agreement — separate from API design

Pillar 1 answers "how do you ask for it." This one answers "what does the
thing you get back actually look like" — and it has to be settled *before*
pillar 1 can be built for real. Concretely, per object type: the
strategy spec's exact fields (drafted, not finalized, in
[../agents-explanation-in-detail/03-strategist.md](../agents-explanation-in-detail/03-strategist.md)§3),
a memory-ledger entry's fields, a shadow-ledger row's fields, and
`capital_allocator`'s output shape (currently a placeholder — see
[../agents-explanation-in-detail/06-capital-allocator.md](../agents-explanation-in-detail/06-capital-allocator.md)).
Every other pillar depends on this one landing first, per object type.

## 6. Immutability — once something is "ground truth," it can't quietly change

A strategy spec, once `risk_gatekeeper` approves it and it goes live, has
to be frozen. `post_trade_review` and `trade_monitor`'s shadow-twin
comparison only mean anything if they're comparing against the *exact*
thing that was actually approved — if the spec could be silently edited
afterward, the whole comparison loses integrity, and so does the
manager-verification mechanism (pillar 9 below) built on top of it.

**Not inventing this rule fresh** — the project already has it, decided
and real: `AngleStorage`'s tier2 (scheduled, frozen once closed) versus
tier3 (triggered, ad-hoc, prunable), from the real storage design doc.
The new data this architecture adds should follow the same tiering
discipline, not a weaker one invented just for vinu-agent.

## 7. Traceability — one ID chain through the whole pipeline

Different from pillar 2 (uniqueness is "does this one row have a stable
ID"). This is "can I start from a closed position and walk *backward*
through `capital_allocator`'s decision → `risk_gatekeeper`'s verdict →
`strategy_lab`'s debate → the original `strategist` spec, with no gap."

**Real precedent already exists for this, not invented here:**
`pnl_attribution`'s `Position.artifact_id`, confirmed directly against
the real schema in `vinu-live/vinu_live/book/schema.py`, links a closed
position back to the trade plan that authored it. That same link has to
thread through every new stage this design adds — `strategy_lab`'s
output, `risk_gatekeeper`'s verdict, `capital_allocator`'s funding
decision — not just the last hop before execution.

## 8. Who's allowed to touch what

Related to pillar 4's external/internal split, but sharper: even
*within* internal storage, should every specialist be able to write to
the memory ledger, or only `post_trade_review`? Should `trade_monitor`
be able to read `capital_allocator`'s allocation data at all?

**Already flagged, not yet decided:** the original architecture doc's
"explicitly deferred" section says exactly this — "`AGENT.md` declaring
which tools a specialist may use is a *convention*, not yet an *enforced*
filtered registry... a risk-critic or idea-generator specialist should
never reach `trade_tool` in practice." That gap was deferred because the
broker wiring was only a test connection at the time. It's a real
question again now that more teams (and more shared stores) are being
added — worth deciding as part of this data architecture rather than
bolting it on after the fact.

## 9. What happens on a partial or failed write

If `strategy_lab` crashes mid-iteration, or a shadow-ledger update is
missed, does whoever reads that data next see an honest "incomplete"
state, or does the gap silently look like "nothing happened"?

This directly matters for the manager-verification mechanism from
[../think-1.md](../think-1.md)§4.1 — the whole point of that check is
cross-referencing a manager's claims against the real underlying records,
which only works if those records are themselves honest about their own
completeness. `team_runs`/`team_tasks` already has a real status enum
(`pending`/`running`/`completed`/`failed`/`cancelled`, mirroring
`SwarmRun`) — the new stores from pillar 3 need the same discipline, not
a simpler "just the final row" version that can't represent "this was
left half-done."

## One more, smaller, not urgent yet

**Retention / pruning.** The memory ledger and shadow ledger both grow
without bound — every symbol, every position, forever. Not decided, and
not urgent to decide now, but worth remembering the project already has a
real answer for the same shape of problem elsewhere: `AngleStorage`'s
tier3 is explicitly "prunable." Reuse that concept rather than deciding
fresh later under time pressure.

## Where to go from here

Nine real pillars, none of them fully answered yet. The three most
load-bearing — because every other pillar either depends on them directly
or inherits their consequences — are **5 (schema/shape)**, **6
(immutability)**, and **7 (traceability)**. Recommended next step: go deep
on those three first, since they're prerequisites for 1, 2, 3, and 9 to
even be answerable concretely.
