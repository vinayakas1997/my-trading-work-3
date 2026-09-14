# vinu-simulator

## What it is

The backtest/paper-rehearsal engine — walks a weight-signal series
against real historical prices, produces performance metrics + a
validation verdict (deflated Sharpe, bootstrap CI, permutation tests).
Not a scheduled loop like the other services — invoked on demand (CLI or
HTTP) by whatever needs a backtest run (`vinu-research`'s
`autopilot`/`run` workflow, an operator).

## Trigger / cadence

No background loop. `vinu-simulator serve` (HTTP API, always up) +
one-shot CLI commands: `run` (execute a backtest), `list` (past runs),
`metrics` (fetch a run's results).

## Pipeline

**`WeightSimulator.run()`** (`engine/simulator.py`), the core mechanism,
in order:
1. Align `weight_signals` and `price_data` to a common calendar (union of
   both indices), forward-fill prices, **raise** if any NaN survives the
   fill (a real gap the caller must know about, never silently zero-fills
   a hole in price history).
2. **T+1 execution shift** — `target_weights_aligned = ws_aligned.shift(1)`.
   A signal observed using data through day D can only be acted on
   starting day D+1; without this shift the engine would fill trades at
   the exact price that produced the signal — textbook look-ahead bias.
   This is the single most important correctness mechanism in the whole
   engine.
3. A rebalance executes on day D only if a new signal was set on day D-1
   (`rebalance_positions`) — trades don't happen every day, only when the
   (already-lagged) target weight actually changed.
4. Per day, in the main loop (numpy arrays pre-extracted once, not
   `.loc[date]` lookups per day — a real perf optimization the code notes
   explicitly): apply the day's cost model
   (`engine/costs.py` — `FlatCostModel` or `AlmgrenChrissCostModel`,
   pluggable), an optional seeded random-reject probability
   (`config.execution_reject_prob`, `np.random.default_rng(config.random_seed)` —
   the only source of randomness in the engine, seeded so a run with
   rejects is still fully reproducible), an ADV volume cap
   (`max_pct_of_volume` — clips a fill and flags `volume_capped=True`
   rather than silently allowing an unrealistic fill size), update
   holdings/cash/portfolio value, record the day's return.
5. `engine/metrics.py::compute_full_metrics` — Sharpe, drawdown, and the
   extended set.
6. `engine/inference.py` — the actual promotion-bar math: deflated Sharpe
   ratio (`deflated_sharpe_ratio`, pinned against the independently
   recomputed Bailey & López de Prado 2014 / VectorBT `nb_trials`
   reference formula), Probabilistic Sharpe Ratio, Mertens standard
   error — this is what `vinu-research`'s `promotion.py::meets_promotion_bar`
   actually reads to decide BENCHING → ACTIVE.
7. `engine/validation.py` — block-bootstrap permutation, price-path
   resampling, Monte Carlo permutation, bootstrap Sharpe CI (BCa) — the
   statistical-significance layer around the raw metrics, not just a
   point estimate.
8. `engine/run_card.py::write_run_card` — a SHA-256-hashed, reproducible
   record of exactly what ran (config, artifact hashes) — so a run's
   result can be verified as not silently re-computed differently later.

**Custom strategy path** (`engine/custom_sim.py::simulate_custom` +
`engine/ast_guard.py`): lets a caller submit actual strategy *code*
(`BaseStrategy` subclass), not just a pre-computed weight series —
`ast_guard.py::validate_strategy_code`/`is_code_safe` statically checks
it before ever executing it (no imports/dunder access/etc. outside an
allowed set) — a real sandboxing step, not just a docstring promise.

**Regime-conditioned performance** (`engine/regime.py`) —
`classify_regime`/`per_regime_performance` break the same backtest's
results down by market regime (not a separate run), so "this strategy
loses money specifically in high-vol regimes" is visible in one output
rather than requiring a separate backtest per regime.

**Attribution** (`engine/attribution.py`) — `match_trades` pairs entry/exit
fills into completed round-trips, `by_symbol_stats`/`by_exit_reason_stats`
break P&L down by symbol and by *why* each trade exited (stop, target,
time, signal-flip), `beta_regression` decomposes return into
market-beta-explained vs. alpha.

## Storage

- `storage/` — run results, keyed by run_id, backing `list`/`metrics`
  reads.
- Run cards (`engine/run_card.py`) — a written, hashed artifact per run,
  separate from the metrics themselves.

## Talks to

- **Outbound**: none in the trading hot path — this is intentionally the
  one service that can run fully offline against historical data with no
  live dependency (though `clients/` exists for fetching price history
  when not supplied directly).
- **Inbound**: `vinu-research`'s research-loop/`autopilot` workflow
  triggers a backtest here and reads results back to decide whether a
  hypothesis is worth authoring into a real trade plan; the resulting
  deflated-Sharpe/PSR numbers are what `promotion.py` checks against the
  BENCHING→ACTIVE bar.
