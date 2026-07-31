---
name: vinu-portfolio
port: 8090
depends_on: [vinu-strategy, vinu-research, vinu-simulator]
---

# vinu-portfolio

## What it does

Portfolio-level aggregation and risk layer — combines strategy weights,
research artifacts, and simulation results into one unified allocation, a
daily "game plan" document, and drawdown/risk status. This is the layer
built out across the Step 04-05 audit work (unified daily plan document,
readiness score, risk budget).

## Scope for this E2E plan

This is where the three strategies stop being evaluated in isolation and
get combined into one portfolio-level allocation with regime-alignment
tilts and risk budget applied. Its `historical_simulation.py` module (new
this session) is the actual CLI entry point for Stage 1's "run the full
system against real history" deliverable:
`vinu-portfolio historical-simulate --days N`.

**Scope decision carried over from the Step 07 audit:** the historical
replay only reuses the risk-parity base + regime-alignment tilt. Outcome
confidence and shock-clustering tilts, and the daily game-plan/risk-budget
layers, are not replayed historically — none of them have a recorded
historical trail (no record of what artifact was ACTIVE with what
calibration accuracy on a given past date). That is a real, documented
scope limit, not an oversight — see
`portfoli-mc-improvement/the-skills-plan-new-discussion-2/steps-to-implement-plan-2/07-validation.md`.

## When it runs

Depends on `vinu-strategy`, `vinu-research`, `vinu-simulator`
(docker-compose `depends_on: strategy-api, research-api, simulator-api`).
Runs after all three strategies have weights and at least one simulation
has run — it's the aggregation point, not a data producer of its own.

## Where data is stored

No local database — this service is a **stateless orchestrator**. It reads
a static `tags.yaml` (`VINU_PORTFOLIO_TAGS_PATH`) for strategy-tag
metadata and otherwise calls upstream services live on every request. A
`VINU_PORTFOLIO_DATA_ROOT` config value exists but no persistent artifact
writes were found in `service.py` — treat this service as **compute, not
storage**.

## Dependencies

- `VINU_STRATEGY_API_URL` (port 8084)
- `VINU_RESEARCH_API_URL` (port 8087)
- `VINU_SIMULATOR_API_URL` (port 8085)
- `VINU_AGENT_API_URL` (port 8086)
- `VINU_CORRELATION_API_URL` / initial-analysis (port 8083)
- `VINU_STOCK_PRICE_API_URL` (port 8081)

## API surface used by this plan

- `GET /portfolio/daily-allocation` — combined weights across strategies.
- `GET /portfolio/daily-game-plan` — the unified plan document with
  readiness score.
- `GET /portfolio/risk/status` — risk budget status.
- CLI: `historical-simulate [--days N]` — the Stage 1 validation entry
  point.

## Known gap as of this document

`historical-simulate` has only been exercised against synthetic data in
unit tests (`tests/test_historical_simulation.py`, 12 tests passing). It
has never been run against real Alpaca-sourced data — that's the first
real Stage 1 milestone once `vinu-stock-price` has cached data.
