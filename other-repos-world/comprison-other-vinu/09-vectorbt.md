# VectorBT

https://github.com/polakowo/vectorbt · 9.0K stars · First released 2017-11-14 · Last updated 2026-08-02

## Advanced Features

- **Numba-JIT vectorized order execution engine** (`vectorbt/portfolio/nb.py:343-505`) — full validation of size/price/fees/slippage/min-size/max-size/size-granularity/reject-probability per order, `buy_nb`/`sell_nb` primitives, and a `SizeType` enum (`Amount`, `Value`, `Percent`, `TargetAmount`, `TargetValue`, `TargetPercent`) that lets you specify orders as target portfolio weights and have the engine compute the delta itself.
- **Explicit signal-conflict resolution engine** with named modes (`ConflictMode.Entry/Exit/Adjacent/Opposite`) resolving simultaneous entry+exit signals based on current position direction — `resolve_signal_conflict_nb`, `vectorbt/portfolio/nb.py:1633-1680`.
- **Configurable stop-order price/slippage resolution** — `resolve_stop_price_and_slippage_nb` supports `StopMarket`, `StopLimit`, or `Close`-price exit semantics, and `generate_stop_signal_nb` supports `Close`, `CloseReduce`, or `Reverse` position behavior on stop-hit — a full state machine for SL/TP/trailing-stop exits, not just a boolean check.
- **Random order-rejection probability** (`order.reject_prob`) — a cheap way to simulate broker-side partial unreliability in backtests.
- **Deflated Sharpe Ratio (DSR)** implementing López de Prado's multiple-testing-corrected Sharpe — `approx_exp_max_sharpe` + `deflated_sharpe_ratio` (`vectorbt/returns/metrics.py:12-36`), taking `nb_trials` (number of strategies/parameter combos tried) explicitly into the correction.
- **`IndicatorFactory` / `SignalFactory`** — a metaprogramming factory (`vectorbt/indicators/factory.py`, `vectorbt/signals/factory.py`) that turns a plain numba calculation function into a class supporting arbitrary parameter grids, broadcasting across many columns (tickers) simultaneously, and caching. This is how vectorbt computes an indicator across thousands of tickers × many parameter combos in one vectorized call.
- **`Drawdowns` record type** (`vectorbt/generic/drawdowns.py`) — tracks decline/recovery duration, active vs. completed drawdowns, and recovery-return ratios as structured records, not just a single scalar max-drawdown number.

## Why It's Trusted / Mature

vectorbt is trusted because its simulation core is deterministic, numba-compiled, and exhaustively validated at the order level — every size/price/fee combination raises explicit, typed rejection reasons (an `OrderStatusInfo` enum) rather than silently producing wrong numbers or a hard crash with no context. Indicator/signal computation is vectorized across the full parameter × asset grid, which is what makes it genuinely fast enough for large universes and dense grid search — this isn't a convenience feature, it's the mechanism that makes exploring thousands of parameter combinations across thousands of tickers computationally tractable at all.

## vs Vinu — Gap & Adoptable Logic

**Gap:** Vina doesn't have a documented vectorized "evaluate N rule-conditions × ~8000 tickers cheaply" computation core — which is exactly what `vinu-screener` needs. vectorbt's `IndicatorFactory` pattern is precisely this: broadcast a calculation function over a wide ticker matrix and a parameter grid, with caching. Also, Vina's simulator likely doesn't have an explicit signal-conflict-resolution mode enum — it's described as ad hoc "signal-conflict detection" in `vinu-live`; vectorbt shows a concrete, finite set of resolution policies worth reusing/naming instead of leaving the policy implicit in scattered conditionals.

**Adopt:**
- `resolve_signal_conflict_nb`'s mode enum — directly portable pattern for `vinu-live`'s signal-conflict detection: replace ad hoc logic with an explicit `Entry/Exit/Adjacent/Opposite` policy keyed by current position direction, so the resolution rule is nameable and testable in isolation.
- `SizeType.TargetPercent`/`TargetValue` order resolution — a clean algorithm for "given current position + target weight + val_price, compute order size" that `vinu-live`/`vinu-portfolio`'s rebalancer could reuse verbatim for turning target weights into concrete order deltas.
- Deflated Sharpe with explicit `nb_trials` correction — check `vinu-research`'s existing deflated-Sharpe gate against this reference formula, specifically whether `nb_trials` (number of strategy variants actually tried before promotion) is being counted and fed in correctly, since that's the crux of the multiple-testing correction and easy to get subtly wrong.
- The `IndicatorFactory` broadcasting pattern — the core architecture idea (not the numba machinery itself) of "one calculation function + declared inputs/params + broadcasting across columns" is the right shape for `vinu-screener`'s rule engine: define each rule condition as a vectorized function over the full price/volume matrix instead of looping per-symbol.
- `order.reject_prob` random rejection — a cheap addition to `vinu-simulator` for fill realism (simulate broker rejects/latency dropouts) alongside the Almgren-Chriss execution model already in use.

## Where Vinu Excels

- **A live, real-broker execution path.** vectorbt is purely a backtesting/research library — there's no live order submission, no kill switch, no book↔broker reconciliation, no reduce_only pattern, because there's no live trading to guard.
- **LLM-assisted strategy research**, versus vectorbt's "you write the signal logic yourself." vectorbt is a computation engine a quant programmer wields directly; Vina's research pipeline generates and reviews candidate strategies through an LLM-assisted, human-gated process.
- **Runtime-configurable risk limits without a code change.** vectorbt's parameters (fees, slippage, size types) are set per backtest run in code; Vina's TradingMandate limits are now live-PATCH-able via the runtime-settings admin API on a running production process.
