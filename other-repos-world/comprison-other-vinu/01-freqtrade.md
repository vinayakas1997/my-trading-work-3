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

---

## Addendum — second pass, 2026-10-02 (local clone: `personal-important/other-reference-repos/freqtrade`)

Scope of this pass: walked the cloned source tree (`optimize/`, `freqai/`, `plugins/`, `strategy/`, `exchange/`, `leverage/`, `rpc/`, `docs/`) and compared it against `high-expectations/chatgpt-version/already-built.md` only — **not** against live `vinu-components/` code. Treat every "gap" below as "not mentioned in already-built.md", and verify before building. Pairlist filters, protections, `RemotePairList` and worst-case stop fills are already covered in the sections above and are not repeated here.

### Why the stars (~55K)
Free, open source, Python, and covers the whole loop (data download → backtest → hyperopt → dry-run → live) with Telegram, REST API and a web UI. CCXT gives 25+ exchanges, FreqAI adds ML, docs are good, strategies are easy to share, and crypto retail interest drives volume. Stars measure tooling and popularity, **not** strategy profitability — it is infrastructure; the edge is the user's. License is **GPL-3.0**: copying code into a distributed product would force GPL; reimplementing ideas from the docs does not.

### Additional features worth knowing (not in the first pass)

- **Lookahead-bias analysis** — `freqtrade/optimize/analysis/lookahead.py`, `lookahead_helpers.py`, docs `lookahead-analysis.md`. Re-runs the backtest on truncated data and flags indicators/signals whose values change once future candles are removed.
- **Recursive-analysis** — `freqtrade/optimize/analysis/recursive.py`, docs `recursive-analysis.md`. Detects indicators whose values depend on how much startup history is loaded (silent backtest-vs-live drift).
- **FreqAI outlier gating** — `freqai/data_kitchen.py`, `freqai_interface.py`, docs `freqai-feature-engineering.md` (§ Outlier detection). Dissimilarity Index (DI), one-class SVM and DBSCAN each mark a live input as "unlike the training data" so the model abstains instead of predicting. Optional PCA dimensionality reduction in the same pipeline.
- **FreqAI sliding-window retraining** — `freqai/data_drawer.py`. Scheduled rolling-window retrain, old models kept/expired, predictions persisted; plus model zoo (LightGBM, XGBoost, sklearn RF, PyTorch MLP/Transformer) and an RL stack (`freqai/RL/`, 3/4/5-action envs).
- **Hyperopt loss library** — `optimize/hyperopt_loss/` (Calmar, Sharpe/Sortino incl. daily variants, max-drawdown variants, profit-drawdown, multi-metric, short-trade-duration).
- **Futures realism in backtests** — `optimize/backtesting.py` + `leverage/`: funding-fee accrual, mark price, liquidation-price updates, Binance leverage tiers.
- **Strategy callback surface** — `strategy/interface.py`: `custom_stoploss`, `custom_roi`, `custom_exit`, `custom_stake_amount`, `adjust_trade_position` (DCA/partial exits), `confirm_trade_entry/exit`, `adjust_entry_price`, `leverage`, `order_filled`.
- **Producer/consumer signal sharing** — `rpc/external_message_consumer.py`, docs `producer-consumer.md`: one bot publishes signals/pairlists to others.
- **Exchange layer** — `freqtrade/exchange/` (Binance, Bybit, OKX, Kraken, KuCoin, Hyperliquid, Gate, Bitget, etc.) with a WebSocket feed (`exchange_ws.py`) and public-data downloader (`binance_public_data.py`).

### Gap vs Vinu (per already-built.md) and adoption priority

| Priority | Item | Why |
|---|---|---|
| 1 | Lookahead-bias + recursive analysis | already-built.md lists holdout/Monte Carlo (overfitting) gates but nothing that tests whether a **feature leaks the future**. Directly relevant to the meta-labeling feature set. Low effort, high return. |
| 2 | Outlier-gating (DI / SVM) as an explicit abstain signal | already-built.md lists "I don't know"/uncertainty as **partial** — spread across several gates with no single abstraction. DI-style "input unlike training data" is a concrete candidate for that single signal. |
| 3 | Scheduled rolling-window retrain with model retention | decay detection exists; a retrain schedule is not mentioned. Take the design, not the code. |
| 4 | Per-symbol loss lockouts (LowProfitPairs/StoplossGuard semantics) | Circuit breakers + kill switch exist; per-symbol lock-with-expiry not mentioned. Overlaps the `IProtection` item already listed above. |
| 5 | CCXT exchange layer + futures-realism backtest + crypto pairlist filters (spread, delist, volume) | Only relevant once Vinu actually trades crypto — already-built.md's *Explicitly deferred* section says nothing executes crypto today. This is the biggest piece of work and the real value of the repo for a crypto move. |
| — | Hyperopt losses, PCA features, producer/consumer | Maybe/low priority; only if automated parameter tuning or multi-bot signal sharing is pursued. |

### Where Vinu is ahead (reconfirmed, don't port)
30-angle market analysis and bull/bear/risk debate; EV-based self-calibrating Trade Score with hard risk:reward floor; DCC-GARCH/Gerber portfolio correlation and composite sizing; thesis-invalidation `live_decision`; post-trade reflection loop and full audit trail; VWAP/TWAP execution slicing (Freqtrade is mostly plain limit/market). Telegram/web-UI/REST/Docker pieces are not needed — Vinu has its own services.
