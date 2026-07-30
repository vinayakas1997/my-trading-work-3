---
name: 07-validation
status: Not Started
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

*(To be filled in after implementation.)*

## Definition of done

- [ ] Historical simulation script exists and runs without errors.
- [ ] Simulation produces all planned metrics and baseline comparison.
- [ ] Simulation results documented with clear analysis.
- [ ] Paper trading (via ShadowEvaluator) runs for at least 1 week of
      market days without critical failures.
- [ ] Paper trading observations documented.
- [ ] Final verdict documented: ready for live, or gaps identified.

## Open risks / assumptions

- Historical data availability is assumed but not verified. If the
  simulation requires price data going back further than what's stored,
  this step may need a data-fetching substep.
- The simplest simulation (daily rebalance, no intraday logic) may not
  capture intraday risk budget behavior — tradeoff between simplicity
  and fidelity, document the choice.
- "Paper trading" with `ShadowEvaluator` only works if `vinu-live` and
  its dependencies can run together. If the environment isn't set up for
  this, there may be infrastructure work before it can run. Flag this
  early.
