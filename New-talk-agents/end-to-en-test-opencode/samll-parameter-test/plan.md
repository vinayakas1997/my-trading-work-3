# Test Plan — Full vinu-components End-to-End Testing

## Context
Full-project test of the vinu-components trading stack (9 FastAPI services in one docker-compose), run end-to-end and per-service. Reference docs: `architecture.md` + `01-block-wise-.md` in `how-to-run-e2e/`.

## Fixed Test Parameters
- **Tickers:** AAPL, TSLA (fully archived 2022–2025)
- **Window:** 2025-07-01 → 2025-12-31 (6 months)
- **Timeframes:** `1D` + `4H` + `1H` (4h unblocked via engine fix)
- **Strategy:** `e2e_easy_sma_crossover` (SMA 20/50 + regime_analysis, no LLM dependency)
- **Mode:** Alpaca paper (`ALPACA_PAPER=true` in `.env`)
- **LLM:** OpenRouter `google/gemma-4-31b-it:free`

## Services (compose)
| Service | Port | Health |
|---|---|---|
| news-api | 8080 | healthy |
| stock-api | 8081 | healthy |
| features-api | 8082 | healthy |
| initial-analysis-api | 8083 | healthy |
| quant-core-api (strategy + simulator) | 8084 | healthy |
| agent-api | 8086 | **DOWN — needs start** |
| research-api | 8087 | healthy |
| portfolio-api | 8090 | healthy |
| live-api | 8091 | **DOWN — needs start** |

## Phase 0 — Full Stack Preflight
1. `docker compose up -d agent-api live-api`
2. Verify all **9** health endpoints from host.
3. Verify agent LLM reachable (`/agent/health`), broker shows paper `configured: true`.

## Phase 1 — Unit Suites (host Python)
- Run `pytest` per service (host Python; `.venv` is WSL-style unusable on Windows).
- Initial-analysis may need to run **in-container** (torch / chronos / timesfm ≈ 10GB wheels won't build on Windows).
- Record pass/fail per service in results table.

Expected test counts (verified):
- vinu-agent 88, vinu-initial-analysis 74, vinu-research 38, vinu-news 29, vinu-tools 17 (now 18 w/ 4h test), vinu-live 14, vinu-simulator 13, vinu-stock-price 12, vinu-infra 12, vinu-portfolio 10, vinu-strategy 8

## Phase 2 — Block Smoke Tests (cross-service)
- **Block 1 (data):** stock candles AAPL/TSLA × 1D/4H/1H → verify row counts and non-zero OHLC.
- **Block 2 (features):** features request per timeframe → parquet written, rows > 0, non-null indicator values.
- **Block 3 (analysis):** initial-analysis run → angles JSON; quant-core strategy evaluate + simulator backtest.
- **Block 4 (portfolio):** portfolio build + evaluate.
- **Block 5 (agent/live):** agent session; live shadow evaluation.

## Phase 3 — Full E2E
1. `run_pipeline.py --ticker AAPL --from-date 2025-07-01 --to-date 2025-12-31` (and TSLA).
2. Real integration tests:
   - `vinu-portfolio/tests/test_e2e_pipeline.py`
   - `vinu-live/tests/test_shadow_evaluator_real_endpoint.py`
   - vinu-agent e2e / integration tests
3. One full scenario: research → approve (direct HTTP workaround) → artifact → live path with `require_confirmation: false`.

## Phase 4 — Known-Gap Verification
Reproduce all 5 known gaps (see `open-gaps-for-future.md`). Mark each REPRODUCED / PARTIAL / FIXED.

## Phase 5 — Deliverables
Write `02-how-to-test-full-project.md` + `scripts/*.ps1` (preflight, unit, smoke, e2e, gap-check) in `how-to-run-e2e/`, populated with actual results.

## Open Decision
- **Research run (Phase 3):** real LLM research loop (`POST /research/run`, OpenRouter free model — slower, rate-limit risk) OR keep main E2E deterministic (Blocks 1–4 + agent/live) and treat the LLM loop as an optional separate step.

## Results Table
| Service / Block | Tests | Status | Notes |
|---|---|---|---|
| (fill during run) | | | |
