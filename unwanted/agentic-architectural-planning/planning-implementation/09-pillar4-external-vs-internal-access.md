---
name: pillar4-external-vs-internal-access
status: boundary-moved-since-writing
purpose: concrete answer to pillar 4 (external vs. internal access) from ../archi-think-1.md -- the boundary itself has since moved for vinu-research specifically (2 of 39 real call sites now in-process, not HTTP); this file's original external/internal split needs reading with that update in mind, not as a correction to throw out.
---

> **The boundary moved, for one specific system.** This file originally
> treated `vinu-research` the same as every other external service —
> read-only, over HTTP, via `services_config`. Since writing this, 2 of
> `vinu-agent`'s 39 real integration points with `vinu-research`
> (`broker/order_guard.py`, `broker/debrief.py`) were rewired to import
> and call `vinu-research`'s Python code **directly, in-process** — see
> [../../../implementation/13-vinu-research-in-process-migration.md](../../../implementation/13-vinu-research-in-process-migration.md).
> `vinu-research` is now something in between "fully external" and
> "vinu-agent's own store": its data is still logically owned by
> `vinu-research`'s package, but `vinu-agent` reads *and writes* it
> directly for those 2 call sites, no network hop, no `services_config`
> URL. The other 37 call sites are unchanged — still real HTTP, still
> exactly what this file describes below. The core rule this file states
> (vinu-agent never writes into a *different* service's database over the
> network) still holds; it just turns out `vinu-research` isn't really a
> separate service's database anymore for the 2 pieces that were
> migrated — it's imported, like `vinu-infra`.

# Pillar 4 — external vs. internal access

Reference: [../archi-think-1.md](../archi-think-1.md) (the 9 pillars).
This is the last of the 9 to get its own file — largely because every
other pillar already ran into this boundary somewhere, so this file is
as much a collection point as new design, similar to how pillar 3 turned
out.

## The rule, stated precisely

**vinu-agent reads from other services; it never writes into their
databases.** Every write vinu-agent performs lands in its own stores
(`team_runs`, `llm_calls`, `strategy_specs`, `memory_ledger`,
`shadow_ledger_snapshots`). Every external system's own data — angle
results, price/fundamentals data, backtest results, real position/order
data — is read-only from vinu-agent's point of view, full stop.

## Confirming the existing pattern already covers every external read

Nothing new needed here — `get_all_angles` (the real, built tool) already
establishes the pattern: a `services_config` dict (e.g.
`{"vinu_initial_analysis": "http://127.0.0.1:8083"}`) injected via
`build_registry()`, an `httpx.Client` call against it, done. Every new
external-reading tool this whole planning pass introduced follows the
identical shape:

| Tool | Reads from | Same pattern as |
|---|---|---|
| `get_all_angles` | vinu-initial-analysis | (the original) |
| `get_angle_history` (pillar 8/§3 in `08-post-trade-review.md`) | vinu-initial-analysis | `get_all_angles` |
| `get_features` / `get_stock_price` / `get_fundamentals` | vinu-tools | (already real, `research` team) |
| `run_backtest` / `run_parameter_sweep` | vinu-simulator / the walk-forward harness | `run_backtest` (already real) |
| `get_portfolio_exposure` | vinu-live (real position data) | same shape, not yet built |
| `get_position_comparison`'s *real* side | vinu-live | same shape, not yet built |

No new connection mechanism required — just more entries in the same
`services_config` and more tools following the same
`httpx.Client`-against-a-configured-base-URL shape already proven.

## Where the internal/external line actually falls — precisely, not just by store name

This matters more than it sounds, because `shadow_ledger_snapshots` has
*both* an internal half and a reference to external data in the same
row: `price` is read from an external market-data feed, but the row
itself, and the fact that it's tracking this particular `spec_id`'s
untouched original plan, is entirely vinu-agent's own internal
bookkeeping. The rule still holds cleanly: vinu-agent *reads* the price
from wherever it already gets price data, but *writes* the resulting
shadow-position row only into its own store — it never writes anything
back to the price feed or to `vinu-live`.

The one place this gets genuinely subtle is `mark_live`/`mark_closed`
(pillar 1/6/8): these `strategy_specs` status transitions are triggered
*by* external events (Phase 6 execution starting, a position closing),
but the row being updated still belongs to vinu-agent. Pillar 8 already
drew this line: the *trigger* is external, but the *write* target is
internal, and whatever credential lets Phase 6 make that call is a
service-auth question, not a change to the read-only-externally rule —
vinu-agent isn't writing into `vinu-live`'s database, `vinu-live`'s own
event handler is writing into vinu-agent's, using vinu-agent's own
narrow `mark_live`/`mark_closed` methods.

## Why this rule is worth stating this bluntly, not just implied

Every one of the 6 proposed teams eventually touches an external system
for real data — it would be easy, team by team, for someone building one
of them later to reach for "just write the result back to vinu-live
directly, it's simpler" as a shortcut once a real integration is in
front of them. Stating the rule once, here, in one place that every other
pillar can point back to, is specifically meant to close that off before
it becomes a real design decision made under implementation pressure
rather than up front.

## Net effect — this pillar closes the set

With this file, all 9 pillars from `archi-think-1.md` now have a
concrete answer, and none of them contradict another:
schema/shape (5) and immutability (6) define what a row looks like and
how it may change; traceability (7) links rows across the
vinu-agent/external boundary this file just drew precisely;
access control (8) governs who — agent or external system — is allowed
to write through that boundary; partial/failed writes (9) makes sure a
row's current state is honestly interpretable; API design (1) collects
the resulting method shapes; uniqueness/dedup (2) settles identity and
the two real duplicate-write risks; and this file, external vs. internal
(4), is the boundary all of the above were implicitly assuming.
