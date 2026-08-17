---
name: phase-2-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 2 -- upgrading risk_gatekeeper and capital_allocator's funding mechanics from a direct, first-come-first-served path to a batched, re-checked one, and stopping capital_allocator from reinventing allocation math that already exists in vinu-portfolio.
---

# Phase 2 -- Funding mechanics upgrade

## What exists today, confirmed real

- `risk_gatekeeper`: built, tested. One spec in, one verdict out. On
  `APPROVED`, a manager-level Python hook (`risk_gatekeeper_hook.py`,
  never an agent-callable tool -- same pattern as every other state-
  mutating action in this project) currently calls `mark_active(...)`
  directly.
- `capital_allocator`: built, explicitly labeled provisional in its own
  code. `allocation_tool.py` ranks currently-ACTIVE artifacts by
  `deflated_sharpe`, funds highest-ranked first, each capped at a fixed
  fraction of budget, until budget runs out.
- `vinu-portfolio` (separate service, Group 3 in the consolidation plan --
  stays a standalone container, not folded into vinu-agent): `service.py`'s
  `PortfolioService.build_portfolio()` computes a real correlation matrix
  and calls `allocate_risk_parity` (inverse-vol risk parity), layered with
  `regime.py`'s vol-quantile bull/bear/sideways/high_vol classification and
  `sizing.py`'s vol-targeting position sizing via `compute_daily_allocation()`.
  `risk_budget.py`'s `compute_risk_budget` does tiered daily-loss
  thresholds per symbol with regime-based size multipliers.

**The correction this phase makes, versus the original mermaid-doc
framing:** `capital_allocator`'s allocation math was flagged as an open
question ("Kelly/risk-parity/other, not decided"). It isn't open --
`vinu-portfolio` already has a working risk-parity engine. This phase
wires `capital_allocator` to call it via HTTP (vinu-portfolio is a
separate, permanent service per the consolidation plan -- not something
to migrate in-process) instead of deciding new math from scratch.
**Confirm vinu-portfolio's actual exposed route path for
`build_portfolio`/`compute_daily_allocation` by reading
`vinu-portfolio/server/routes_*.py` directly before implementing** -- this
plan knows the real function names from `service.py` but hasn't confirmed
their HTTP-exposed paths this session.

## What this phase builds

**1. New holding state: `PEND` ("approved, pending allocation").**
`risk_gatekeeper_hook.py` changes so `APPROVED` moves the artifact into
`PEND` instead of calling `mark_active` directly -- funding becomes
`capital_allocator`'s decision, made across a batch, not this stage's
alone. Same gated-status-transition pattern `SqliteStrategyStore` already
enforces for every other state change -- `PEND` is a new valid state in
that same machine, not a new mechanism.

**2. `capital_allocator` runs on a fixed cadence, not per-candidate.**
Collects the whole `PEND` batch accumulated since its last pass, ranks it
together, then funds and `mark_active`s the winners. Turns "whoever
finishes first gets the budget" into an actual comparison. The cadence
interval itself is a tuning parameter, not decided here (see
`New-talk-agents/new-thinking/new-restructure/mermaid-explanation.md`'s
open questions).

**3. Ranking calls `vinu-portfolio`, doesn't recompute risk parity
locally.** Where `allocation_tool.py` currently ranks by `deflated_sharpe`
alone, it instead sends the `PEND` batch (plus the existing ACTIVE book)
to `vinu-portfolio`'s `build_portfolio`/`compute_daily_allocation` and
uses the returned weights to decide which `PEND` candidates get funded
and at what size. `deflated_sharpe` can still inform *ranking within* what
`vinu-portfolio` returns as viable, but the actual position-sizing math
comes from the real risk-parity engine, not a fixed-fraction rule.

**4. Staleness re-check right before funding.** Because candidates now
wait for the next cadence run instead of funding immediately, the
portfolio can look meaningfully different by the time funding executes.
`capital_allocator` re-runs a cheap exposure snapshot check immediately
before funding -- not a full `risk_gatekeeper` re-review, just confirming
the picture hasn't moved since the batch was assembled.

**5. NEW-vs-NEW correlation, not just NEW-vs-existing.** `risk_gatekeeper`
only ever evaluates one candidate against the existing book
(`get_portfolio`, real, reused). Nothing else checks whether several
individually-approved `PEND` candidates are themselves correlated with
each other. `capital_allocator` validates the whole funded set together
-- this is naturally covered by routing the batch through
`vinu-portfolio`'s correlation matrix (item 3 above) rather than being a
separate check to build.

**6. `risk_gatekeeper`'s exposure check also stops reinventing math.**
Its portfolio-fit check can call `vinu-portfolio`'s `compute_risk_budget`
(tiered per-symbol thresholds, regime-aware) instead of whatever ad hoc
sizing logic it uses today for the initial APPROVED/REJECTED call --
keeps the two gates (initial approval, final funding) consistent with the
same real risk math instead of two different implicit models.
