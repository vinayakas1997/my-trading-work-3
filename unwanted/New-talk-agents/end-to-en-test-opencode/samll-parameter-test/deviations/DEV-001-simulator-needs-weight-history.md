# DEV-001 — Strategy `evaluate` produces current-day weights; simulator needs a historical series

- **Component:** vinu-strategy `service.py:evaluate` + vinu-simulator `service.py:simulate` (StrategyClient.get_weights)
- **Source of expected behavior:** plan.md Phase 2 Block 3 "quant-core strategy evaluate + simulator backtest"
- **Phase:** 2

## Documented / expected
Evaluate the strategy, then run the simulator backtest on the same strategy for the window — implying the backtest consumes that strategy's signals over 2025-07-01 → 2025-12-31.

## Actual behavior
`POST /strategy/strategies/e2e_easy_sma_crossover/evaluate?symbols=AAPL` computes and persists **one** weight row dated today (2026-08-11), not a daily series for the backtest window. `POST /simulator/simulate` calls `GET /strategy/weights?from_ts=...&to_ts=...` and fails with:
```
{"detail":"No weight data found for strategy 'e2e_easy_sma_crossover' in range 2025-07-01 to 2025-12-31","error":"validation_error"}
```
The deterministic path uses `POST /simulator/simulate/custom` with inline strategy code instead (that's what `run_pipeline.step_simulator` and `run_deterministic.py` do), which backtests fine.

## How discovered
Block 3: called `/simulator/simulate` with the strategy after a successful `evaluate`; got the "No weight data found" error (0.26s). Checked `GET /strategy/weights` — only today's row present.

## Impact
MED — the "evaluate → backtest same strategy" flow advertised by the plan isn't directly wired; there's no walk-forward/daily weight generator in vinu-strategy. The `/simulate/custom` path covers deterministic backtesting, but strategy-based backtests over a past window can't be run via `/simulator/simulate` without a weight-history producer.

## Workaround used
Use `/simulator/simulate/custom` with inline strategy code (pipeline's standard path) — 1.62s for AAPL, full metrics returned.

## Root cause
Known — vinu-strategy `evaluate` is a single-timestamp signal computation; nothing generates a daily weight series for historical dates (no walk-forward endpoint).

## Status
OPEN

## Evidence
- `evidence/03-analysis/simulator-aapl.json` (custom backtest result)
- `GET /strategy/weights?strategy=e2e_easy_sma_crossover` → single row dated 2026-08-11
