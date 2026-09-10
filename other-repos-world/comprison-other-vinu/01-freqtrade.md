# Freqtrade

https://github.com/freqtrade/freqtrade · 54.1K stars · First released 2017-05-17 · Last updated 2026-09-08

## Advanced Features

- **Composable pairlist pipeline** — an ordered chain of pluggable filters/generators (`VolumePairList`, `AgeFilter`, `PriceFilter`, `SpreadFilter`, `RangeStabilityFilter`, `PrecisionFilter`, `MarketCapPairList`, `PerformanceFilter`, `CrossMarketPairList`), driven off `freqtrade/plugins/pairlist/IPairList.py` and orchestrated by `freqtrade/plugins/pairlistmanager.py`. Each filter declares its own config schema via `PairlistParameter` TypedDicts, plus a `supports_backtesting` flag (`NO`/`BIASED`/`YES`) so the framework warns when a filter would leak lookahead bias into a backtest.
- **`RemotePairList`** (`freqtrade/plugins/pairlist/RemotePairList.py`) — pulls a candidate whitelist from an external HTTP endpoint: bearer-token auth, TTL cache, `keep_pairlist_on_failure` fail-open fallback. An externally-computed scanner feeding straight into the live bot.
- **Protection framework** (`freqtrade/plugins/protectionmanager.py`, `freqtrade/plugins/protections/`) — `StoplossGuard` (N stoplosses in a lookback window → lock pair/global), `MaxDrawdown` (equity or ratio-based drawdown halt), `CooldownPeriod`, `LowProfitPairs`. All implement `IProtection` and return a `ProtectionReturn` lock with an expiry — a generic halt-with-cooldown state machine, not one-off logic per guard.
- **Backtest fill realism** — `_get_close_rate_for_stoploss` / `_get_order_filled` (`freqtrade/optimize/backtesting.py:574-830`) implement "worst realistic case" stop/trailing-stop fills within a candle: only fills if `LOW <= rate <= HIGH`, and trailing-stop-in-same-candle assumes the most pessimistic price path.
- **FreqAI** (`freqtrade/freqai/freqai_interface.py`, `data_kitchen.py`, `data_drawer.py`) — an adaptive/online-retraining ML layer with its own feature-engineering pipeline and prediction persistence, fully decoupled from strategy code.

## Why It's Trusted / Mature

Freqtrade's credibility rests on dry-run/live parity — the exact same code path runs a strategy in backtest, dry-run, and live, so what you validated is what actually executes. On top of that, it has one of the largest libraries of composable, declaratively-configured plugins in the space (pairlist filters, protections) that a non-programmer can assemble from JSON config alone, plus an actively-maintained exchange abstraction (via CCXT) covering 20+ venues. The `supports_backtesting` flag on every pairlist filter is a small but telling detail — it shows the maintainers explicitly designed against a known failure mode (lookahead bias silently entering a backtest through a filter that only makes sense with future data), rather than leaving that to the user to catch.

## vs Vinu — Gap & Adoptable Logic

**Gap:** Vina has no chainable, hot-swappable pairlist-filter architecture — `vinu-screener` is being designed from scratch, while Freqtrade already has ~15 production-hardened filter implementations to draw the taxonomy from. Vina also has no generic "protection" abstraction unifying stoploss-guard/drawdown-guard/cooldown into one reusable lock/unlock state machine — `vinu-live`'s halt policy and cooldown-after-losses are closer to one-off bespoke logic than a pluggable framework.

**Adopt:**
- Port the `IPairList` filter-chain pattern wholesale for `vinu-screener`: each rule = a class with a `filter_pairlist()` method, a declared JSON-schema of parameters, and a `supports_backtesting` marker for lookahead-bias warnings. This gives Vina's "user-defined rule conditions" a clean, testable, addable-without-touching-core plugin model instead of one monolithic rule evaluator.
- Port the `IProtection`/`ProtectionReturn` lock abstraction — generalize `vinu-live`'s halt-policy/cooldown-after-losses into the same shape: pluggable protection objects that emit `(lock_pair_or_global, until_timestamp, reason)`, reusable for correlation-trim, OOD-flatten, and kill-switch triggers alike, instead of each having its own bespoke lock logic.
- Port `_get_close_rate_for_stoploss`'s worst-case-within-candle fill logic directly into `vinu-simulator` for more conservative/realistic stop and trailing-stop fills, instead of assuming exact-price fills.
- Port `RemotePairList`'s bearer-token + TTL-cache + fail-open-on-failure pattern as a template for how `vinu-screener`'s output could later be consumed by another Vina service over HTTP — matches Vina's existing bearer-token auth model already used for the runtime-settings admin API.

## Where Vinu Excels

- **A formal statistical promotion gate before anything trades.** Freqtrade lets a strategy go live the moment a user enables it — there's no equivalent of `vinu-research`'s deflated-Sharpe + holdout + stress-test gate standing between "backtested well" and "trading real money." A strategy that overfits a Freqtrade backtest can be live within minutes.
- **LLM-assisted research integrated with the live pipeline.** Freqtrade's FreqAI is online-retraining ML bolted onto strategy execution, not a research-and-promotion workflow — Vina's LLM-driven research service producing artifacts that must clear a gate before `vinu-agent` will ever trade them is a meaningfully different (safer) shape.
- **`reduce_only` threaded consistently as a first-class exemption.** Freqtrade's protections (`StoplossGuard`, `MaxDrawdown`) lock *all* trading including exits during a lock window in some configurations; Vina's guards are built from the ground up to always exempt risk-reducing orders, so a halt never traps you in a losing position.
- **Purpose-built for one broker, done deeply** — Freqtrade's 20+-exchange CCXT abstraction is breadth Vina deliberately doesn't need; that focus lets Vina harden Alpaca-specific behavior (book↔broker reconciliation, exact order-guard semantics) more thoroughly than a framework spread across dozens of exchanges realistically can per-venue.
