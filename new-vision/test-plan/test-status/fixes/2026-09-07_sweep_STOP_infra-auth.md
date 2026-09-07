# 2026-09-07 sweep STOP (all 3 tickers) → fix
- Failure: research team runs `736c28d490a3` (AAPL), `488a923de4a6` (MSFT),
  `163c1a3a3be9` (NVDA) all ended `STOP`, 0 artifacts. Agent self-diagnosis:
  "simulator returning 401 Unauthorized". Second wave (`81a7c63e80b5` NVDA)
  STOPped on empty price data (fresh DB, no backfill yet).
- Root causes:
  1. `VINU_API_KEY` enforcement is global (`vinu_infra/server.py:102`) but no
     internal client sent `Bearer` — every service-to-service hop 401'd.
     Proven via `/features/AAPL` returning upstream stock-api 401.
  2. Stock watchlist empty after data wipe → `count:0` candles → simulator
     422 "No weight data generated".
- Fix: `vinu_infra/auth.py:internal_auth_headers()` + `ResilientClient`
  auto-Bearer + per-service client headers (~45 files); seeded
  stock/news watchlists (AAPL/MSFT/NVDA) + backfill (1.1M rows; 138/131/131
  daily bars); follow-ups: unknown recipe params now 400, infra backtest
  errors raise `InfrastructureError` (fail fast), upstream 401→502 mapping,
  `X-Data-Empty` header on empty candles, zero-data summary warnings,
  `scripts/setup-secrets.ps1` for Windows hosts.
- Evidence after fix: `GET /features/AAPL` 200; `POST
  /research/sweep/candidate` run_ids `45bad5f9…` (sharpe -0.606),
  `e4d85c93…`; NVDA summary 27/28 angles with data; wrong params →
  `400 Unknown params for recipe 'crossover'`; empty symbol →
  `x-data-empty: true`.
