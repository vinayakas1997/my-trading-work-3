---
name: 04-daily-plan-document
status: Completed
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

The core of this step (dataclasses, merge function, route, CLI, initial
tests) already existed uncommitted in the repo before this session — this
entry documents it against the real DoD, closes the two gaps found, and
flips the status from the stale "Not Started" it had been logged as.

- `SymbolPlan` / `DailyGamePlan` dataclasses (`vinu_portfolio/game_plan.py`)
  define the document shape from substep 1: per-symbol weights/multipliers,
  forecast/invalidation/`p_failure` from the TradePlan, `plan_status`, plus
  portfolio-level readiness flags.
- `PortfolioService.compute_daily_game_plan()` (`service.py`) is the merge
  function from substep 2 — calls `compute_daily_allocation()`, fetches
  each symbol's TradePlan via `_fetch_trade_plan()`, merges into the shape
  above.
- `GET /portfolio/daily-game-plan` (`server/app.py`) and
  `vinu-portfolio daily-game-plan` (`cli.py`) expose it, per substep 3.
- **Gap found and closed this session:** the readiness score originally
  only counted per-symbol TradePlan coverage (`n_with_plan / n_total`),
  not the regime-fetch and account-equity fail-open paths that
  `compute_daily_allocation()` already has. Broadened to count all three
  as live-or-not data points (`readiness_flags.regime_available` /
  `.equity_available` added) — see `daily-allocation/SKILL.md`'s
  "Unified daily game plan" section for the exact formula. This changes
  `readiness_score`'s value and the `game_ready` gate's behavior; existing
  tests asserting old score values were updated to match, not just left
  broken.
- **Gap found and closed this session:** no test covered the
  all-data-unavailable edge case (substep 4). Added
  `test_all_data_unavailable_edge_case` and
  `test_readiness_score_reflects_regime_and_equity_availability` to
  `test_game_plan.py`.
- `daily-allocation/SKILL.md` updated with a new section describing the
  unified plan and the readiness formula (substep 5) — was untouched
  before this session.

## Definition of done

- [x] Document shape designed and documented.
- [x] Merge function implemented and tested.
- [x] Route and/or CLI exposes the unified plan.
- [x] Readiness score correctly reflects data source availability.
- [x] Tests cover normal, degraded, and empty-portfolio cases.
- [x] Skill doc updated.

## Open risks / assumptions

- TradePlans may not exist for all symbols in the portfolio. The merge
  must handle "no TradePlan found" gracefully — either skip enrichment
  for that symbol or include planless symbols with a flag.
- The readiness score definition ("3/5 symbols have live data") is
  intuitive but needs a precise formula — what counts as "live data"?
  (Regime fetch succeeded? Calibration route responded? Both?) Define
  this in substep 1.
