---
name: 04-daily-plan-document
status: Not Started
phase: 3
code: D4
depends_on: [02-shock-clustering, 03-probabilistic-exit]
unlocks: [05-risk-budget]
---

# Step 04 — Unified Daily Plan Document

## Why this step

Today, the daily plan is split across two disconnected artifacts: per-symbol
TradePlans (direction, forecast, risk, exits for one symbol) and the
portfolio-level `compute_daily_allocation()` (weights across symbols). No
single document merges them into one combined picture. A human (or the agent)
has to mentally reconcile two outputs to understand "what's the plan for
today, across all positions, with full context."

Additionally, both artifacts currently **fail open** silently — if regime
data is unavailable for one symbol, the allocation just goes neutral without
saying so. A fully-informed day and a half-blind day look identical in the
output. The plan needs a **readiness score** that surfaces degradation.

## What we're achieving

- One combined daily artifact that merges per-symbol TradePlans under the
  portfolio-level allocation, with full transparency on why each symbol
  got its weight.
- A readiness/confidence score that explicitly states "3/5 symbols have
  live regime data, 2 are using defaults" — not silent degradation.

## Where it matters in the future

This is the actual output users will see — the "daily game plan." Everything
else (allocation engine, shock clustering, probabilistic exits, risk budget)
feeds into this single document. Without it, all the intelligence built so
far exists in disconnected pieces.

## How it connects to other steps

- **Depends on Step 02** — shock correlation data feeds the risk picture.
- **Depends on Step 03** — probabilistic exits are part of the plan.
- **Unlocks Step 05** — the risk budget operates on the unified plan.

## Substeps

1. **Design the document shape.** Define the output format. At minimum it
   should contain:
   - Date and overall readiness score.
   - Per-symbol section: ticker, weight, base weight (risk-parity before
     tilts), regime multiplier, outcome multiplier, final weight, position
     size in dollars (when equity data is available).
   - Per-symbol plan: direction, forecast, probabilistic exit bands,
     shock correlation with other positions, confidence level, staleness
     status.
   - Portfolio-level: total exposure, cash ratio, VaR estimate (if
     available), drawdown status, circuit breaker distance.
   - Readiness flags: which data sources were available, which were
     degraded/unavailable.
   Choose a format (JSON dict, Pydantic model, dataclass) that is both
   machine-readable and human-inspectable — the same design principle as
   `compute_daily_allocation()`'s per-strategy breakdown.

2. **Build the merge.** Write a function (likely on `PortfolioService` or a
   new dedicated class) that:
   - Calls `compute_daily_allocation()` to get weights + multipliers.
   - For each weighted symbol, calls/reads its TradePlan.
   - Merges them into the unified shape from substep 1.
   - Computes the readiness score by counting which data sources were
     successfully fetched vs. failed open.

3. **Expose the result.** Add a route (e.g.
   `GET /portfolio/daily-game-plan`) and/or update the existing
   `GET /portfolio/daily-allocation` to return the enriched document.
   Add a CLI command matching the existing `daily-allocation` shape.

4. **Write tests.** Cover: the merge works with real-style data, readiness
   score correctly reflects degraded sources, edge case with no active
   strategies, edge case with all data unavailable.

5. **Update skill docs.** Ensure `daily-allocation/SKILL.md` describes the
   unified plan and readiness score.

## What was actually built

*(To be filled in after implementation.)*

## Definition of done

- [ ] Document shape designed and documented.
- [ ] Merge function implemented and tested.
- [ ] Route and/or CLI exposes the unified plan.
- [ ] Readiness score correctly reflects data source availability.
- [ ] Tests cover normal, degraded, and empty-portfolio cases.
- [ ] Skill doc updated.

## Open risks / assumptions

- TradePlans may not exist for all symbols in the portfolio. The merge
  must handle "no TradePlan found" gracefully — either skip enrichment
  for that symbol or include planless symbols with a flag.
- The readiness score definition ("3/5 symbols have live data") is
  intuitive but needs a precise formula — what counts as "live data"?
  (Regime fetch succeeded? Calibration route responded? Both?) Define
  this in substep 1.
