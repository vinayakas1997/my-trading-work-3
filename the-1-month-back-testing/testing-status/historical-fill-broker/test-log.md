# historical-fill-broker — Test Log

## What will be tested / Expected output

- Unit-level: feed `HistoricalFillBroker` a known historical price series
  and a scripted sequence of buy/sell calls; confirm fills land at the
  next bar's open (not the decision-bar close), confirm cash/equity math
  is internally consistent (cash + holdings*price == equity, every step).
- Confirm `get_account()` starts at the configured initial cash
  ($100k, matching the real paper account) and evolves correctly after
  fills.
- Confirm `get_clock()` correctly reports `is_open: false` on a weekend
  date inside the replay window.
- Confirm a live (non-replay) session is completely unaffected —
  `TradeTool` still instantiates `AlpacaBroker()` exactly as before when
  `_as_of` is unset.
- Full detail: [../../scope-responsibilities/02-historical-fill-broker.md](../../scope-responsibilities/02-historical-fill-broker.md)

## Bug / Fix Log

### Design verification (2026-08-03) — reusing `vinu_simulator.engine` works
- **Cost models confirmed as scoped** (`vinu_simulator/engine/costs.py`):
  `FlatCostModel` (lines 41-70) and `AlmgrenChrissCostModel` (lines 73-137)
  both exist with the described interface — `buy_cost(price, shares, volume,
  volatility)` / `sell_proceeds(...)` / `daily_borrow_cost(...)`. Item 2 can
  import these directly; no new cost math needed in `vinu-agent`.
- **T+1 / no-same-bar-fill discipline confirmed** (`vinu_simulator/engine/
  simulator.py:98-114`): `target_weights_aligned = ws_aligned.shift(1)` with
  the exact comment the scope quotes — "a signal observed using data through
  day D can only be acted on starting day D+1... this is look-ahead bias."
  Item 2's "fill at the next available bar after `as_of`" rule mirrors this
  correctly.
- **Metrics confirmed** (`vinu_simulator/engine/metrics.py`):
  `compute_performance_metrics(portfolio_values: pd.Series, daily_returns:
  pd.Series, ...)` at line 32 and `compute_full_metrics` at line 230 exist as
  item 4's plan expects. No hand-rolled Sharpe/drawdown needed.
- **No design gaps found in this item's build plan.** The broker's price
  source (`vinu-stock-price` candles API) is confirmed to serve per-symbol
  OHLCV keyed by `bar_ts` (verified live on AAPL). One thing to remember at
  implementation: the fill-price source and the agent's own price tool read
  the *same* API, so a missing-bar day may surface as a silently-skipped fill
  — the step-0 coverage gate (item 3) is the mitigation, not an additional
  check here.

### Verification results (2026-08-03) — direct broker test, bypassing the LLM

**Why direct, not through the real 20-day agent replay:** the real replay run
(`run-2026-07-06-2026-07-31`, see `day-stepper-replay-harness/test-log.md`)
never produced a single successful `submit_order` call — the local qwen
model consistently failed to pass required tool arguments (empty `{}`
arguments, `KeyError: 'symbol'`), so this broker's fill logic had never
actually been exercised by a real call, only code-reviewed. Verified it
directly instead, same "bypass the LLM for the first pass" pattern used for
`options_tool.py`. Script:
`scratchpad/test_historical_broker.py` (temp, not committed — logic is
what matters, reproducible from this description).

- **Fresh account defaults correctly**: `get_account()` on a
  never-before-seen `state_path` returns `cash: 100000.0` (matches
  `DEFAULT_INITIAL_CASH`), not an error or a zero.
- **T+1 fill confirmed, no lookahead**: `submit_order(AAPL, 10, buy)` with
  `as_of=2026-07-06T13:30:00Z` filled at `fill_date: 2026-07-07` (the next
  trading day), price 315.06 — never the decision-day price. Matches
  `WeightSimulator`'s `shift(1)` discipline as scoped.
- **Cost model applied, not free execution**: buy cost (3155.33) exceeds
  raw notional (10 × 315.06 = 3150.60) by the configured slippage+fee —
  confirmed non-zero transaction cost.
- **State persists across broker instances**: a second `HistoricalFillBroker`
  instance pointed at the same `state_path` (simulating a new day/message in
  the real harness) read back the exact same cash/position left by the
  first instance — continuity across the month is real, not an in-memory
  illusion that would reset every message.
- **Partial sell correct**: sold 5 of 10 shares, fill again landed on the
  next trading day after the sell's `as_of`, remaining qty (5) and reduced
  cost basis correct.
- **Rejections correct**: an oversized buy (1,000,000 shares) correctly
  rejected `insufficient_cash` with the actual cash/cost numbers, not a
  crash; an oversized sell (999 shares against a 5-share position) correctly
  rejected `insufficient_position`.
- **Weekend clock correct**: `get_clock()` for a Saturday (2026-07-11)
  returns `is_open: false`.

### Bug-1 — position's `current_price`/mark never updated on a sell, only a buy
- **Found during:** the direct verification above, checking `get_positions()`
  after a partial sell.
- **Date:** 2026-08-03
- **Symptom:** `submit_order(..., side="sell")` fills at a real price (e.g.
  309.84) but the position's `last_close` field (used as `current_price` /
  `market_value` / `unrealized_pl` in `get_positions()`) was only ever set
  on the **buy** branch (`pos["last_close"] = fill_price`, buy branch only).
  After a sell, `get_positions()` kept reporting the stale price from the
  last buy, understating how current the mark actually was.
- **Reproduction:** buy AAPL, then sell part of it at a different price;
  call `get_positions()` — `current_price` still shows the buy price, not
  the sell price.
- **Severity:** minor (paper-portfolio display accuracy only; cash/qty
  accounting was already correct) but directly feeds item 4's P&L report,
  so worth fixing rather than deferring.
- **Root cause:** `vinu_agent/broker/historical_broker.py`'s sell branch
  (previously lines 179-190) updated `cash`, `qty`, `cost_basis` but never
  `pos["last_close"]`.
- **Fix applied:** added `pos["last_close"] = fill_price` to the sell
  branch, mirroring the buy branch.
- **Verification:** re-ran the direct test script — `get_positions()` after
  the same partial sell now shows `current_price: 309.84` (the actual sell
  fill price), `market_value`/`unrealized_pl` updated accordingly.
- **Status:** fixed.

Cross-reference: a related reporting bug (the replay harness's fallback
account snapshot showed `cash: null` instead of this broker's real default)
lived in `run_month_replay.py`, not in this broker — logged as Bug-4 in
`day-stepper-replay-harness/test-log.md`, not duplicated here.

_More entries as implementation proceeds._
