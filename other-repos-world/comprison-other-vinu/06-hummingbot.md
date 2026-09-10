# Hummingbot

https://github.com/hummingbot/hummingbot · 18K stars · First released 2019-04-02 · Last updated 2026-09-09

## Advanced Features

- **`TripleBarrierConfig`** (`hummingbot/strategy_v2/executors/position_executor/position_executor.py` + `hummingbot/strategy_v2/models/executors.py`) — a single config object bundling stop_loss, take_profit, time_limit, and a `TrailingStop(activation_price, trailing_delta)`, with a `new_instance_with_volatility_adjustment(volatility_factor)` method that rescales all barriers by realized volatility. The executor's `control_barriers()` runs `control_stop_loss` / `control_trailing_stop` / `control_take_profit` / `control_time_limit` every tick, each independently able to trigger a market close.
- **Partial-fill-aware order renewal** — `renew_take_profit_order()` / `control_take_profit()` re-quotes the take-profit limit order if `amount_to_close` drifts from what's live, handling partial fills gracefully rather than assuming an order either fully fills or doesn't.
- **Profitability-based kill switch** (`hummingbot/core/utils/kill_switch.py`) — `ActiveKillSwitch.check_profitability_loop()` polls realized P&L every 10s and calls `trading_core.shutdown()` once a configured loss (or gain) threshold is crossed, independent of any single strategy's own logic — a portfolio-wide backstop.
- **Executor orchestration layer (`strategy_v2`)** (`hummingbot/strategy_v2/executors/executor_orchestrator.py` + `executors/executor_base.py`) — strategies emit declarative `Executor` configs (position, DCA, grid, arbitrage, TWAP, XEMM) that run as independent state machines with their own lifecycle (`on_start`, `control_task`, `control_shutdown_process`), decoupling "what to trade" from "how the order lifecycle is managed."
- **MQTT-based remote command/control bus** (`hummingbot/remote_iface/mqtt.py`) — `MQTTCommands` exposes `start/stop/config/import/status/history/balance_limit` as message-bus RPCs, i.e. a live remote config/control channel — conceptually similar to what Vina's new runtime-settings admin API does, but over pub/sub rather than REST, plus a `balance_limit` remote knob for capital caps.
- **`AsyncThrottler`** (`hummingbot/core/api_throttler/async_throttler.py`) — per-limit-id token-bucket-style rate limiting shared across concurrent async tasks hitting exchange APIs.

## Why It's Trusted / Mature

Hummingbot is trusted for live, real-money automated trading against many exchanges because of the executor state-machine model: every open position is a self-contained, independently auditable object with clearly defined exit conditions (the triple barrier) checked every tick, rather than exit logic scattered ad hoc through strategy code. That structural discipline means a bug in one strategy's entry logic can't silently corrupt how an already-open position's exits are managed — the executor owns that regardless of how the position was opened. The kill switch operating at the P&L level (not the strategy level) gives a portfolio-wide backstop that survives strategy bugs specifically because it doesn't depend on the buggy strategy code recognizing its own failure.

## vs Vinu — Gap & Adoptable Logic

**Gap:** Vina's `vinu-live` has contingency/invalidation rules and a halt policy, but nothing as reusable/composable as the `TripleBarrierConfig` + volatility-scaling pattern — each position type in Hummingbot gets stop/target/time/trailing barriers "for free" from one config object, whereas Vina's rule engine appears to handle each contingency type as its own logic path. Vina also lacks a pub/sub-style remote command bus for control-plane actions (start/stop/config), though the new runtime-settings REST API partially covers the config half of that.

**Adopt:**
- `TripleBarrierConfig.new_instance_with_volatility_adjustment()` — a concrete mechanism for scaling stop/target/trailing thresholds by realized volatility; directly portable into `vinu-live`'s invalidation rule engine so contingency thresholds aren't static regardless of how volatile a symbol currently is.
- The trailing-stop state machine (`TrailingStop` dataclass + the `control_trailing_stop` control loop) — activation-price + trailing-delta pattern applicable to `vinu-live`'s OOD/emergency-flatten and reduce_only trim logic.
- The profitability kill switch loop — a periodic, decoupled-from-strategy P&L monitor that calls a hard shutdown; a simple pattern to strengthen `vinu-agent`'s kill switch to be P&L-threshold-driven, not just manual/limit-driven.
- The executor-as-state-machine architecture — each live position/order as an independent object with `on_start`/`control_task`/`control_shutdown_process` — worth considering for how `vinu-live` manages concurrent frozen trade plans, especially as the number of simultaneously open positions grows.

## Where Vinu Excels

- **A pre-trade statistical validation gate.** Hummingbot's strategies are user-authored and go live as soon as configured — there's no equivalent of `vinu-research`'s deflated-Sharpe/holdout/stress-test gate standing between "strategy configured" and "strategy trading real capital."
- **LLM-assisted research generating the strategies themselves**, not just executing user-written ones. Hummingbot is purely an execution framework — it has no research/discovery layer at all.
- **Purpose-built for equities, not adapted from crypto/market-making.** Hummingbot's `TripleBarrierConfig` and executor model are designed around crypto market-making/arbitrage assumptions (continuous 24/7 markets, thin order books); Vina's guards (market-hours checks, halt policy, book↔broker reconciliation) are built specifically around US equities' actual trading-session structure.
