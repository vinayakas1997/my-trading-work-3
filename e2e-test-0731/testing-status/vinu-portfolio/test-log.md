# vinu-portfolio — Test Log

**Status:** VERIFIED (2026-08-02) — aggregation/readiness endpoints work on
real data. `historical-simulate` CLI hit a symbol-mapping limit (universe-wide
strategies), logged below.

## Verification results (2026-08-02)

- **`GET /portfolio/health`** → ok. **`GET /portfolio/state`** → lists 6
  strategies (4 built-ins + `e2e_easy_sma_crossover` +
  `e2e_medium_trend_vol_filter`).
- **`GET /portfolio/weights`** → `target_weight: 0.1667` × 6 = **1.0002**
  (sum≈1.0 within float tolerance) ✓.
- **`GET /portfolio/daily-allocation`** → 6 strategies, position sizes
  computed, aggregation wiring to strategy-api live (200s on every call).
- **`GET /portfolio/daily-game-plan`** → readiness_score 0.25,
  `readiness_flags` (regime_available true, equity_available true,
  game_ready false), `n_symbols 6`, per-strategy plan_status `no_plan`.
- **`GET /portfolio/risk/status`** → regime null, aggregate n_positions 1
  (the `*no_positions` sentinel), total_daily_pnl 0, game_plan_readiness
  0.125 — no crash on no-live-positions state.

### Note: `historical-simulate` CLI can't map universe-wide e2e strategies

- The CLI (`historical_simulate_main` in `vinu_portfolio/cli.py:77-97`)
  derives per-strategy symbols as `s["symbol"]`, but the e2e strategies are
  **universe-wide YAMLs** (empty `symbol`), so `symbols=[]` → returns empty
  and it prints `"no historical price data available"`. This is a real
  integration mismatch between the CLI's per-symbol assumption and the
  whole-universe strategy model — **not** a data-backfill problem (SPY is
  in the stock catalog and fetchable). Logged as a follow-up; the HTTP
  aggregation layer above (which is the Stage 1 aggregation deliverable)
  works correctly.

## Bug / Fix Log

_Nothing logged yet — testing has not started._
