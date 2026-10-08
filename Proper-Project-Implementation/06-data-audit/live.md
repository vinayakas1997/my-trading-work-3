# Data audit: vinu-live

Checked 2026-10-08 on the running stack (`live-api`, port 8091; `/data` 2.1 MB: `trade_plan_book.db`, `execution_log.db`, `live_decision.db`, `breaker_day_equity.json`). Paper mode, base 20 dollars.

## What triggers it
- **Scheduler cycle** (on its configured interval): syncs the book to the broker, gets the daily allocation from portfolio, turns weights into order slices, runs the guards, sends orders to the agent's trade route, records the result.
- **Live-decision loop** (daily bars): for each (ticker, YAML strategy) pair it checks the strategy's preconditions on the newest bar and keeps a stage (idle, watching, armed ...).
- **Trade-plan orchestrator** and **feedback cycle**: handle approved trade plans, rebalance requests, and send realised trades to initial-analysis.

## Data items

### L1 The book  `trade_plan_book.db: open_positions` (0), `closed_positions` (1), `fills` (1)
- **Format:** position id, symbol, side, qty, entry price, pnl, open/close times, exit price, close cause, plan id, `account_mode`. The one closed row is AAPL 2 shares, entry 336.80, closed 2026-10-08 03:21 at 336.80, pnl 0.0: it was my drill's manual round trip, closed by the book-sync (P60), which cuts at the entry price because the broker's exit price is not known to it.
- **Access:** `GET /live/capital` (open positions at cost, results), plan routes. **Consumers:** capital ledger (free cash), order guard (via the ledger), breaker, cooldown and symbol lockout, scheduler (ownership), portfolio capital plan (held money, win/loss statistics via `results`). **Verdict:** `used well` (the core record of what the system holds).

### L2 Scheduler orders  `execution_log.db: scheduler_executions` (4 rows, paper)
- **Format:** one row per slice: symbol, side, qty, outcome (submitted, rejected, ...), reference price, spread, fill price, slippage in bps, `account_mode`. Now: 3 rejected, 1 submitted and filled (mean slippage 6.5 bps).
- **Access:** `GET /live/executions` (summary + recent). **Consumers:** the summary route, the scheduler's own idempotency (bought symbols, unresolved orders), the capital ledger (buys still filling). No other service reads `/live/executions`. **Verdict:** `used well` inside live; `no outside reader`.

### L3 Live decisions  `live_decision.db`: `live_decisions` (0), `live_decision_open_positions` (0), `strategy_stage_state` (26, all idle), `strategy_stage_transitions` (0), `live_snapshots` (42), `live_poll_cursor` (7)
- **Format:** stage per (ticker, strategy) with the indicator values of the last checked bar; snapshots of angle outputs; a cursor per ticker/timeframe. The 26 stages are 7 tickers (AAPL, MSFT, GOOGL ...) against the YAML strategies, not against research strategies.
- **Access:** `GET /live/decisions/{ticker}/{strategy_id}`, `/decision-context/...`, `/snapshots/...`, `/journal`. **Consumers:** agent (`decision-context` 2 files, `decisions` 2 files); journal route (no outside caller). **Verdict:** `idle` (no decision made yet).

### L4 Trade records are in four places that do not join
- the book (`closed_positions`, with pnl), the order log (`scheduler_executions`, with slippage), the live-decision journal (`/journal`, only positions opened by a live decision: now 0 although the book has a closed row), and the agent's `trade_audit.log` (every order and refusal, with the real fill). `/live/tca/slippage` reads only plan fills (count 0) while `/live/executions` shows one slippage of 6.5 bps. A question like "what did this trade cost and earn, from decision to close, in paper or real money?" cannot be answered from one place (DA-L1).

### L5 Day-start equity  `breaker_day_equity.json` (`{"date": "2026-10-07", "equity": 96613.96}`)
- One number per day, the paper account's equity, kept for the breaker's old percentage rule. With a real-money base the breaker uses the base instead (P61), so this file is a leftover that still shows the 96,613 figure. **Consumers:** the breaker in the no-base case. **Verdict:** `legacy`.

## Where live reaches the market
portfolio daily allocation (empty today) -> scheduler -> order guard (agent) -> Alpaca paper. Exits and the book sync run every cycle regardless.
