---
name: vinu-live
port: 8091
depends_on: [vinu-portfolio, vinu-agent, vinu-stock-price]
---

# vinu-live

## What it does

Live trading orchestration — runs allocation/trade-plan/feedback cycles,
shadow-evaluates research artifacts (the `ShadowEvaluator` built and wired
in the prior audit plan's Step 01), and executes trades via TWAP/VWAP
slicing.

## Scope for this E2E plan

**Out of scope for Stage 1.** This service is the Stage 2 (paper trading)
and Stage 3 (live capital) engine. It's listed here for architectural
completeness, but no work on it is planned until Stage 2 actually starts —
per the earlier scope decision, `vinu-agent`'s broker/paper-trading
credential wiring is explicitly deferred to Stage 2.

## When it would run (Stage 2+, not now)

Depends on `vinu-portfolio`, `vinu-agent`, `vinu-stock-price`
(docker-compose `depends_on: portfolio-api, agent-api, stock-api`). This is
the top of the dependency chain along with `vinu-agent` — everything else
must be working first.

## Where data is stored — CORRECTED 2026-08-02, this was wrong

This section previously claimed position state might be in-memory only.
Checked directly: `vinu_live/book/positions.py`'s `BookBackend` is a real
`SQLiteBackend` (`open_positions`/`closed_positions`/`fills` tables,
`data/book.db`), and `docker-compose.yml` mounts `./data/live:/data` as a
genuine host bind-mount (`read_only: true` with `tmpfs` only on `/tmp`
and `/home/app/.cache` — `/data` itself is not tmpfs). Position state is
durable and will survive a container restart. See `../stage-2-plan.md`
for the correction record. One live restart smoke-test is still worth
doing before Stage 2 starts (reading code isn't the same as observing
it), but this is not a blocker.

## Dependencies

- `VINU_PORTFOLIO_API_URL` (port 8090)
- `VINU_AGENT_API_URL` (port 8086)
- `VINU_STOCK_PRICE_API_URL` (port 8081)
- `VINU_RESEARCH_API_URL` (port 8087)
- `VINU_INITIAL_ANALYSIS_API_URL` (port 8083)

## Execution configuration

- Style: `twap` or `vwap`, with `twap_slices` and `max_slippage_pct` —
  relevant once Stage 2 starts, not for Stage 1's daily-rebalance
  simulation.

## API surface (for future reference, Stage 2)

- `POST /live/cycle` — full allocation/trade cycle.
- `POST /live/shadow-evaluate` — paper-trading evaluation without real
  execution.
- `GET /live/status` — current live state.

## Known gap as of this document

Not evaluated in depth for this document since it's out of scope — flagged
here so nobody assumes Stage 1 exercises this service. It does not.
