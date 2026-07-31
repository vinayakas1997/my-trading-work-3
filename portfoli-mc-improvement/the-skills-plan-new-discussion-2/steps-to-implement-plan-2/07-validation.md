---
name: 07-validation
status: In Progress
phase: 5
code: D7
depends_on: [05-risk-budget, 06-agent-integration]
unlocks: []
---

# Step 07 — Validation: Historical Simulation + Paper Trading

## Why this step

Everything built across both plans — the sweep engine, gatekeepers, governor,
daily allocation, shock clustering, probabilistic exits, risk budget, agent
integration — has never been tested as a complete system against real
historical data or in a paper-trading environment. Individual components
have unit tests. The system as a whole has never been validated.

This is the final gate before live trading. It answers: "does the whole
thing actually work?" without risking capital.

## What we're achieving

- A historical simulation that runs the complete allocation + game plan
  system against past market data and measures performance (Sharpe,
  drawdown, win rate, etc.).
- The `ShadowEvaluator` paper-trading pipeline (wired in Step 01) runs
  the system against live market data without real capital.
- A clear pass/fail decision on whether the system is ready for live
  trading.

## Where it matters in the future

This is the last pre-live step. After this, the system either proves
itself ready or reveals gaps that need fixing first.

## How it connects to other steps

- **Depends on Step 05** — risk budget is part of the system being tested.
- **Depends on Step 06** — agent integration is part of the system being tested.
- **Unlocks nothing** — this is the final step.

## Substeps

1. **Design the historical simulation.** Define:
   - Time period to test (last 1 year? 2 years? Multiple regimes?).
   - Data sources (do we have historical data for this period?).
   - Metrics to measure (Sharpe, max drawdown, win rate, avg trade
     duration, Calmar ratio).
   - Baseline to compare against (equal weight? Risk-parity only? Buy and
     hold SPY?).
   - How to handle look-ahead bias (regime classification on historical
     data must not see future data — verify the implementation).

2. **Build the simulator.** Create a script that:
   - Loads historical data for the test period.
   - At each rebalance point (daily), runs `compute_daily_allocation()`
     with the full pipeline (regime read, outcome confidence, shock
     clustering, probabilistic exits, risk budget).
   - Records the resulting weights and simulated P&L.
   - Outputs performance metrics and comparison to baseline(s).
   This does not need to be a full event-driven backtester — a simple
   daily-rebalance simulation is sufficient for validation.

3. **Write the simulation tests.** Validate that the simulator produces
   reasonable results (weights sum to 1.0, no NaN positions, P&L is
   computed correctly from returns × weights).

4. **Run the paper trading validation.** Trigger `ShadowEvaluator` (now
   wired from Step 01) against live market data. Let it run for a defined
   period (at minimum 1-2 weeks of market days). Monitor output for
   anomalies — weights diverging, unhandled errors, readiness score
   dropping.

5. **Document results.** Write up:
   - Historical simulation results (metrics vs baseline).
   - Paper trading observations.
   - Any gaps or failures found.
   - Verdict: is the system ready for live trading? What (if anything)
     needs to be fixed first?

## What was actually built

Substeps 1-3 (design, build the simulator, test it) are done. Substeps 4-5
(run paper trading, document real results) are **blocked on
infrastructure this session confirmed is not present**, not skipped —
see below.

**Substep 1 (design):**
- Time period: configurable lookback (`--days`, default 730 ≈ 2 years),
  not hardcoded, so a future run can widen it once real data exists.
- Data source: `vinu-stock-price`'s historical candles endpoint
  (`GET /stock/candles/{symbol}?interval=1d&days=N`), the same source
  `_fetch_benchmark_regime()` already uses live.
- Metrics: Sharpe, max drawdown, win rate, Calmar, annualized/total
  return — all four requested metrics implemented
  (`compute_performance_metrics()`).
- Baselines: equal-weight (same symbols, static 1/N, no tilts) and
  buy-and-hold on the configured benchmark symbol (`SPY` by default) —
  both computed alongside the tilted-strategy result for direct
  comparison, per substep 1's ask.
- Look-ahead handling: at each rebalance point `i`, regime is classified
  from `benchmark_returns.loc[:as_of]` (an expanding window truncated at
  `as_of`, not the full series — `classify_current_regime()`'s internal
  quantile threshold would otherwise leak future volatility into past
  regime labels) and weights are computed from `returns_df.iloc[:i+1]`,
  then held for the *next* day's realized return only. Verified by a
  dedicated test walking through the exact weights-vs-realized-return
  arithmetic independently of the simulator's own bookkeeping
  (`test_portfolio_return_matches_weights_dot_realized_returns`).
- **Scope decision, documented not silently narrowed:** only the
  risk-parity base + regime-alignment tilt are replayed (reusing
  `PortfolioService.allocate_risk_parity()` and
  `_regime_alignment_multiplier()` directly, not re-implementations).
  Outcome-confidence and shock-clustering tilts, and the Step 04/05
  game-plan/risk-budget layers, are **not** replayed — none of them have
  a historical trail to reconstruct from (which artifact was ACTIVE with
  what calibration accuracy on a past date, live account equity, live
  positions — none of this is recorded anywhere to replay against).
  Simulating them would mean fabricating history, not testing it.

**Substep 2 (build the simulator):**
- `vinu_portfolio/historical_simulation.py` (new) —
  `run_historical_simulation()` (pure, offline, walk-forward),
  `compute_performance_metrics()`, `fetch_historical_returns()` /
  `fetch_benchmark_returns()` (async, hit the live candles endpoint).
- `vinu-portfolio historical-simulate [--days N]` CLI command wired in
  `cli.py`, following the existing `daily-game-plan`/`risk-status`
  pattern. Fetches live strategies, fetches each strategy's underlying
  symbol's historical returns (a proxy for the strategy's own returns —
  simpler than the live pipeline's `_fetch_strategy_returns`, which
  reconstructs returns from actual historical weights/positions; documented
  simplification, not an oversight, consistent with substep 2's "does not
  need to be a full event-driven backtester").

**Substep 3 (simulation tests):** `tests/test_historical_simulation.py`
(new, 12 tests) using synthetic returns data — covers exactly what the
DoD asks: weights sum to 1.0 every day
(`test_weights_sum_to_one_every_day`), no NaN positions/returns
(`test_no_nan_positions_or_returns`), P&L computed correctly from
returns × weights (`test_portfolio_return_matches_weights_dot_realized_returns`,
verified against manual compounding in
`test_pnl_matches_manual_compounding`), plus edge cases (empty data, too
few observations, zero-variance returns).

**Substep 4 (run paper trading) — blocked, confirmed this session:**
Traced whether a real run is currently possible and it is not, for two
independent reasons:
1. No historical price data exists locally for the simulator to run
   against — no candle parquet/database files under `vinu-stock-price`'s
   data directory (confirmed by listing it), and `vinu-stock-price`
   itself is not running in this environment (`curl` to its health
   endpoint fails to connect). The step's own "Open risks" section
   flagged exactly this ("historical data availability is assumed but
   not verified") — it was not verified because it isn't there.
2. `ShadowEvaluator` paper trading requires `vinu-live` + its
   dependencies running continuously against live market data for "at
   least 1 week of market days" (the DoD's own words) — that requires
   real elapsed time and a persistently running deployment, neither of
   which a single work session can provide regardless of what code
   exists.
- **Not done, not fabricated:** no historical simulation numbers or
  paper-trading observations are recorded anywhere in this repo. Do not
  trust any Sharpe/drawdown figure attributed to this step unless it's
  backed by an actual logged run.

**Substep 5 (document results) — cannot be honestly done yet**, for the
same reason: there is nothing real to document. This section will be
filled in with actual numbers once substep 4 is actually run.

## Definition of done

- [x] Historical simulation script exists and runs without errors —
      verified against synthetic data (`tests/test_historical_simulation.py`,
      12 passed); has not yet been run against real historical market
      data (none available in this environment — see substep 4 above).
- [x] Simulation produces all planned metrics and baseline comparison —
      structurally verified (Sharpe/max drawdown/win rate/Calmar/returns,
      strategy vs. equal-weight vs. benchmark, all present in
      `SimulationResult`); not yet exercised with real data.
- [ ] Simulation results documented with clear analysis — blocked, no
      real run exists yet to document.
- [ ] Paper trading (via ShadowEvaluator) runs for at least 1 week of
      market days without critical failures — blocked, requires a live
      multi-day deployment window, not achievable in one session.
- [ ] Paper trading observations documented — blocked, same reason.
- [ ] Final verdict documented: ready for live, or gaps identified — not
      yet reachable; the honest interim verdict is "the validation
      tooling exists and is tested, but the system has not actually been
      validated against real data or real paper trading yet." Treat the
      system as **not yet cleared for live trading** until this step's
      remaining boxes are checked for real.

## Open risks / assumptions

- **Confirmed this session (not just "assumed"):** historical data is
  **not** available — no candle data files under `vinu-stock-price/data/`,
  and the service isn't running in this environment. This step does need
  a data-fetching/backfill substep before substep 4 can run for real;
  that's now a known blocker, not a guess. `vinu_stock/backfill/` exists
  in that repo and looks like the right starting point, not traced
  further here — out of scope for this session.
- The simplest simulation (daily rebalance, no intraday logic) may not
  capture intraday risk budget behavior — tradeoff between simplicity
  and fidelity, document the choice.
- Also confirmed: the simulator replays strategy returns via each
  strategy's underlying symbol's price returns, not the live pipeline's
  actual historical-weights-based `_fetch_strategy_returns()` — a
  simplification appropriate for a "not a full event-driven backtester"
  v1, but means simulated strategy returns won't exactly match what the
  live pipeline would have computed for the same dates.
- "Paper trading" with `ShadowEvaluator` only works if `vinu-live` and
  its dependencies can run together. If the environment isn't set up for
  this, there may be infrastructure work before it can run. Flag this
  early.
