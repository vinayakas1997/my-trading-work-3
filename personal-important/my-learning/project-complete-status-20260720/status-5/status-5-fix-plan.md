# Remaining Gaps — Fix Plan

Companion to [status-5.md](./status-5.md). All five buildable items are now done. What's left needs a
broker/paper account to *use*, not to build — the account itself isn't something code can create.

---

## Priority 1 — Wire `PortfolioDrawdownMonitor` into an actual scheduled loop — DONE

**What equity source to use turned out to be the real design question**, not just "who calls
`.update()`." `vinu-portfolio` only ever computes target *weights*, not a live dollar portfolio value —
the actual account equity lives wherever the broker connection is, which is agent-api
(`AlpacaBroker`). Rather than giving `vinu-portfolio` its own Alpaca credentials (a second place
holding broker access, for no good reason), added a read path through agent-api instead:

**What was done:**
1. Added `GET /broker/account` to agent-api (`vinu-agent/vinu_agent/server/routes_broker.py`),
   wrapping `AlpacaBroker.get_account()`. Returns `{"configured": false, ...}` — not an error — until
   a broker account exists, so this is forward-compatible with zero changes needed once one does.
2. New `vinu-portfolio/vinu_portfolio/drawdown_scheduler.py`: `run_once()` polls that endpoint and
   feeds the equity into `PortfolioDrawdownMonitor.update()`; `monitor_main_loop()` wraps it in the
   same `while True: cycle(); time.sleep(interval)` pattern as `research-decay-scan`.
3. New `vinu-portfolio monitor` CLI subcommand, and a new `portfolio-drawdown-monitor` service in
   `docker-compose.yml`, polling every 300s by default against `drawdown_halt_threshold` (`-0.20`).
4. Tests: 3 in `vinu-agent/tests/test_routes_broker.py`, 4 in
   `vinu-portfolio/tests/test_drawdown_scheduler.py`.

---

## Priority 2 — Stop-loss enforcement via bracket orders — DONE

**What was done:**
1. `AlpacaBroker.submit_order()` (`vinu-agent/vinu_agent/broker/alpaca.py`) now accepts
   `take_profit_price`, `stop_loss_price`, `stop_loss_limit_price`. Passing both attaches Alpaca's
   native `order_class: "bracket"`; passing only one attaches `order_class: "oto"` — both are
   documented, stable Alpaca order-class contracts, not guesswork.
2. `TradeTool` (`vinu-agent/vinu_agent/tools/trade_tool.py`) exposes these as new tool parameters and
   threads them through to `submit_order()`, so the LLM (or `vinu-live`, via the new `/broker/order`
   route below) can attach a real resting stop/target at entry time instead of relying on a human to
   watch the position and submit the exit manually later.
3. Tests: 6 new in `vinu-agent/tests/test_alpaca_broker.py` covering plain/bracket/oto/stop-limit
   payload construction.

---

## Priority 3 — Market-hours / stale-data check — DONE

**What was done:**
1. `AlpacaBroker.get_clock()` wraps Alpaca's `/v2/clock` endpoint.
2. New `TradingMandate.require_market_open` (default `True`) and `OrderGuard._check_market_open()`
   reject orders while the market is closed — fails open with a warning if the clock call errors,
   same posture as every other broker-dependent check in `OrderGuard`. Can be disabled per-mandate for
   strategies that intentionally queue orders (e.g. `time_in_force: "opg"`).
3. Tests: 4 new in `vinu-agent/tests/test_order_guard.py`.

(Data-staleness on the price side is already covered by Priority B from status-3's volume/volatility
check, which reads live bars rather than cached values — no separate mechanism needed here.)

---

## Priority 4 — Fix `vinu-live`'s known execution bugs — DONE

All five sub-bugs, verified against real code rather than assumed:

1. **Calls agent-api routes that don't exist.** `_fetch_positions()` called `/broker/positions` and
   `_execute_plan()` called `/broker/order` — neither existed on agent-api. Added both:
   `GET /broker/positions` (wraps `AlpacaBroker.get_positions()`) and `POST /broker/order`, which
   deliberately delegates to `TradeTool.execute()` rather than calling the broker directly — so
   `vinu-live`'s orders go through the exact same `OrderGuard` checks (kill switch, artifact gate,
   market hours, concentration) as the LLM's path, not a second, weaker code path around them.
   `_fetch_prices()` also called a `/prices/{symbol}` route that never existed anywhere — fixed to
   call `vinu-stock-price`'s `/candles/{symbol}` directly, since agent-api owns the broker connection,
   not price data.
2. **No close-order generation.** Confirmed: `SignalTranslator.translate()` only ever looped over
   `target_weights`, so a symbol currently held but dropped from the strategy's target weights was
   never sold — positions could only grow or rebalance, never fully close on exit. Fixed: positions in
   `current_positions` absent from `target_weights` are now treated as target weight `0.0` and
   generate a real close instruction.
3. **Hardcoded portfolio-value fallback.** `portfolio_value = sum(...) or 1_000_000.0` silently
   fabricated a million-dollar balance any time the computed value was falsy — including the ordinary
   case of zero current positions. Fixed: portfolio value now comes from the same `/broker/account`
   equity endpoint added for Priority 1; falls back to priced positions, then to an explicit, logged,
   configurable `fallback_portfolio_value` — never a silent magic number.
4. **TWAP-only.** Added `plan_vwap()` and `compute_volume_profile()` to `execution.py` — VWAP splits
   each order across slices weighted by a real historical intraday volume profile (bucketed by each
   day's relative position within its own session, avoiding a timezone-dependent market-hours
   assumption), falling back to equal weights per-symbol whenever volume data is missing or malformed.
   Selectable via `LiveConfig.execution_style` (`"twap"` default, or `"vwap"`).
5. **Ignores `--interval` flag.** Root-caused, not just re-verified: `pyproject.toml` registers a
   *second* console-script entry point, `vinu-live-worker`, pointing directly at `worker_main` —
   pip's generated wrapper calls that with zero arguments, so `args` was always `None` on that path,
   and `--interval` from `docker-compose.yml`'s `command: ["vinu-live-worker", "--interval", "3600"]`
   was silently dropped in favor of the config/env default. It happened to match in the current
   compose file (both 3600), which is exactly how this kind of bug hides. Fixed: `worker_main` now
   parses `sys.argv` itself when `args` is `None`, factored into a separately-tested
   `resolve_worker_interval()`.

Tests: 21 new across `vinu-live/tests/{test_signal_translator,test_execution,test_scheduler,test_cli}.py`
(previously zero tests existed for this package), 4 new in `vinu-agent/tests/test_routes_broker.py`
for the two new routes. `docker-compose.yml` updated with `VINU_STOCK_PRICE_API_URL` for both
`live-api` and `live-worker`.

---

## Priority 5 — Portfolio-level correlation/concentration enforcement at order time — DONE

Sequenced after Priority 4 since it needed `vinu-live`'s execution path to actually be real before
protecting it made sense.

**What was done:**
1. New `TradingMandate` fields: `max_symbol_concentration_pct` and `max_pairwise_correlation` (both
   default `1.0` = no restriction).
2. `OrderGuard._check_portfolio_concentration()` re-fetches `vinu-portfolio`'s current target weights
   and correlation matrix at order time — independent of whatever weights were computed upstream, so
   drift between `vinu-portfolio` and execution is actually caught here, not just theoretically
   possible to catch. Only applies to buy orders (a sell reduces exposure, so blocking it on
   concentration grounds would be actively harmful). Correctly maps strategy name to symbol via the
   `weights` payload rather than assuming they're the same string — the correlation matrix is keyed by
   strategy name, not ticker, in `vinu-portfolio`'s actual response shape. Fails open on error, same
   posture as every other check in this class.
3. Tests: 7 new in `vinu-agent/tests/test_order_guard.py`.

---

## What's left — genuinely not buildable without the account

**No broker/paper-trading account exists.** This was never a code gap — it's an external prerequisite.
Every check and code path above is written and tested against Alpaca's documented API contracts and
against mocked responses, but none of it has executed against a real account yet. That's the one
remaining item, and it's not something further code changes can close.
