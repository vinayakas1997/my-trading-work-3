---
name: stage-2-plan
status: definition-phase
purpose: single source of truth for the Stage 2 (paper trading) validation plan — what we're testing, with what data, over what period, before any paper order is placed
---

# Stage 2 Validation Plan (2026-08-02 draft)

**This is a definition document, not a test log.** Nothing described here
has been executed yet. Mirrors the discipline `full-plan.md` used for
Stage 1: scope, duration, and success criteria fixed before Stage 2
starts, so there's no mid-run scope drift once real (paper) orders are
live.

## Why this exists

Stage 1 (full historical simulation, 2022-01-01 → 2026-06-30, AAPL/TSLA/JNJ)
is now genuinely complete and independently verified — real Sharpe (0.65),
CAGR (14.8%), max drawdown (-38.9%), backed by a stored, checksummed
simulation run (`data/simulator/simulations/14/1487b17d.../run_card.json`).
Per `full-plan.md`'s own three-stage table, Stage 2 is the next milestone:
a live paper-trading account, ~1 week of real market days, no capital at
risk. This document defines it.

## Blockers — both claims below turned out to be false, corrected 2026-08-02

The two items originally listed here as blockers, sourced from the
`scope-responsibilities/` docs written during Stage 1, were checked
directly against the running system and both turned out to be wrong.
Leaving the correction in place (not just deleting it) so nobody
re-discovers the same false alarm from the stale doc:

1. ~~`AlpacaBroker` credential wiring has not been done.~~ **False.**
   `ALPACA_API_KEY`/`ALPACA_API_SECRET` already exist in
   `vinu-components/.env` and `agent-api` already has `env_file: .env`
   like every other service. Verified live: `GET
   http://localhost:8086/agent/broker/account` →
   `{"configured":true,"equity":100000.0,"cash":100000.0,"portfolio_value":100000.0}`.
   The broker is already connected to a live $100k Alpaca paper account.
   Nothing to wire.

2. ~~`vinu-live` position tracking is unverified/likely in-memory.~~
   **False.** `vinu-live/vinu_live/book/positions.py` uses a real
   `SQLiteBackend` (`BookBackend`, `data/book.db`) with proper
   `open_positions`/`closed_positions`/`fills` tables — not in-memory.
   `docker-compose.yml:326-327` mounts `./data/live:/data` as a genuine
   host bind-mount (only `/tmp` and `/home/app/.cache` are `tmpfs`,
   per lines 336-338) — the same durable-volume pattern used by every
   other service in this stack. Position state will survive a container
   restart.

**Remaining verification, not a blocker:** nobody has actually placed a
paper order and restarted the container to *prove* the above end-to-end
(reading the code and the compose file is strong evidence, not a live
test). Worth one real smoke test before Stage 2's clock starts — see
`the-stage-2-claude/` for the detailed plan, item 3.

## Scope — proposed, not yet locked

Carried over from Stage 1 where it makes sense; flagged where it doesn't
directly transfer:

| Item | Stage 1 | Stage 2 proposal |
|---|---|---|
| Tickers | AAPL, TSLA, JNJ | Same three — no reason to change; keeps results comparable to Stage 1's baseline |
| Strategies | Easy (SMA crossover), Medium (ADX/vol filter), Complex (LLM forecast) | Same three tiers, run through `vinu-live` instead of the historical simulator |
| Data source | Alpaca historical bars/news | Alpaca **paper** trading API + live market data feed |
| Duration | One-off retrospective | ~1 week of market days (per `full-plan.md`'s stage table) |
| Capital | None (simulated) | None (paper account, not real money) |
| Execution style | N/A (batch simulation) | TWAP/VWAP slicing per `vinu-live`'s existing config (`twap_slices`, `max_slippage_pct`) — needs a concrete choice, not yet made |

**Open questions this doc does NOT answer yet** (need a decision before
Stage 2 locks, same as Stage 1's tickers/dates/strategies got locked
up front):
- Rebalance cadence — daily? Once at start? `vinu-portfolio`'s
  `daily-game-plan` implies daily, but that hasn't been confirmed as the
  Stage 2 cadence.
- What counts as pass/fail for Stage 2 — Stage 1 had no gate (it just had
  to produce numbers). Stage 2 is a go/no-go input to Stage 3 (real
  capital), so it needs an actual bar (e.g., no execution errors over the
  full week, position state survives at least one restart, P&L
  reconciles daily against `vinu-live`'s own accounting).
- Monitoring — who/what checks on this daily while it runs unattended for
  a week? Stage 1 was interactive; Stage 2 is not.

## What Stage 2 will actually exercise (once started)

Per `architecture.md`'s scope legend, this activates the grey/dashed
Stage-2-only components for the first time:

1. `vinu-agent` — `AlpacaBroker` places real (paper) orders via
   `POST /broker/order`; `/broker/account`, `/broker/positions` used for
   state checks.
2. `vinu-live` — `POST /live/cycle` runs the actual allocation → trade →
   feedback loop against the paper account, not a simulator.
3. Everything from Stage 1 (`vinu-strategy`, `vinu-portfolio`,
   `vinu-research`, `vinu-initial-analysis`, `vinu-tools`,
   `vinu-stock-price`, `vinu-news`) continues running underneath, now
   feeding a live loop instead of a batch backtest.

## Related documents

- [full-plan.md](full-plan.md) — Stage 1 definition (superseded status:
  Stage 1 now complete, see `testing-status/`).
- [architecture.md](architecture.md) — full system diagram; Stage 2
  components are the grey/dashed nodes.
- [scope-responsibilities/vinu-live.md](scope-responsibilities/vinu-live.md),
  [scope-responsibilities/vinu-agent.md](scope-responsibilities/vinu-agent.md)
  — the two components this stage activates for the first time.
