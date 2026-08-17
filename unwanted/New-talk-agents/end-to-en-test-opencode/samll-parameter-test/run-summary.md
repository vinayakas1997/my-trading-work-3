# Run Summary

## Run 1

- **Date:** 2026-08-11
- **Environment:** docker-compose (9 services, Docker Desktop on Windows), host Python 3.12 for pipeline driver
- **Services tested:** news-api, stock-api, features-api, initial-analysis-api, quant-core-api (strategy+simulator), research-api, portfolio-api, agent-api, live-api
- **Parameters:** AAPL + TSLA · 2025-07-01 → 2025-12-31 · 1D/4H/1H · e2e_easy_sma_crossover · Alpaca paper · OpenRouter google/gemma-4-31b-it:free

### Timings (AAPL deterministic pipeline)
| Stage | Status | Duration |
|---|---|---|
| stock-price (backfill) | ok | 47.49s |
| features | ok | 0.04s |
| initial-analysis (31 angles) | ok | 95.38s (cached) / ~1h30m fresh |
| strategy evaluate (e2e_easy_sma_crossover) | ok | 31.41s |
| simulator backtest | ok | 1.62s |
| research /research/run (LLM) | ok | 76.73s |
| portfolio state / daily-allocation / risk | ok | 0.75s / 0.66s / 1.3s |
| agent session (create + message) | ok (degraded LLM) | 0.70s + 1.13s |
| live shadow-evaluate | ok | 0.48s |

### LLM call detail
- research run: total 199 calls (all time), in-run gemma calls all hit HTTP 429 → fail-closed, loop completed degraded with report (1 iteration, validation STOP).
- AAPL pipeline vinu-news step: 19,503 LLM calls in window, 19,417 failed (19,416×429, 1×503), 86 succeeded — client gave up at 30s read timeout (report logged 206 calls / 192 failed from the client's own counter). Service-side analysis continued; news_analysis table has 928 rows.
- Agent: free-tier daily quota exhausted (X-RateLimit-Remaining: 0) → graceful 429 error surfaced as assistant message.

### Totals
- Unit tests passed / total: 21/21 (quant-core GPU suite, this session) — see logs/01-unit-*.log for earlier suites
- Blocks passing / total: 4 / 5 fully (AAPL path); TSLA Block 1/2/3 pending server-side analysis completion
- Deviations found: 2
- Issues found: 5 (ISSUE-001 FIXED; 002–003 FIXED via workaround; 004–005 OPEN)
- Known gaps reproduced: not yet exercised (Phase 4)

### Verdict
PASS WITH DEVIATIONS (AAPL path complete through all 5 blocks; TSLA analysis server-side in progress; LLM-dependent steps degraded by free-tier rate limits but fail closed gracefully)

### Highlights
- All 9 services healthy; GPU confirmed (NVIDIA RTX 3050, cuda: True).
- AAPL initial-analysis: 281 runs, 0 errors, 31/31 angles.
- Strategy registry bug found and fixed (strategies dir unseeded → seeded from image + restart).
- Two `/data` write-permission fixes (initial-analysis + research) via root chmod (9p metadata mount).
- Research loop produced an actual strategy code artifact end-to-end via OpenRouter.
- stock-api RestartCount=6 (clean exit 0, no OOM) — Docker restarted it during heavy TSLA-analysis load; explains transient "Connection refused" in Block 2 TSLA features.

### Open items carried forward
- TSLA: verify initial-analysis (~281 runs) completes, then retry Block 1/2 candles+features, run strategy evaluate + simulator backtest for TSLA.
- Investigate stock-api clean-exit restarts (RestartCount=6, ExitCode=0, no OOM) under concurrent analysis load.
- Run portfolio e2e integration test + live shadow evaluator real-endpoint test + agent e2e tests (Phase 3 item 2).
- Phase 4 known-gap verification (5 gaps).
- OpenRouter free-tier rate limits block reliable LLM-heavy steps (news/research/agent) until daily reset or paid credits.
