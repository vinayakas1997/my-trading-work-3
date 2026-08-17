# Results Table (Master Matrix)

Service / block × expected × actual × status.

| # | Service / Block | Expected | Actual | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| 0.1 | agent-api up | healthy | healthy (31 skills, LLM gemma-4-31b-it:free) | PASS | evidence/00-preflight/ | |
| 0.2 | live-api up | healthy | healthy | PASS | evidence/00-preflight/ | |
| 0.3 | broker paper configured | configured:true | configured:true (alpaca) | PASS | evidence/00-preflight/ | |
| 1.1 | vinu-news unit | 29 pass | | | | |
| 1.2 | vinu-stock-price unit | 44 pass | | | | |
| 1.3 | vinu-tools unit | 150 pass | | | | |
| 1.4 | vinu-initial-analysis unit | 74 pass | | | | |
| 1.5 | vinu-quant-core (strategy+simulator) unit | 21 pass | | | | |
| 1.6 | vinu-research unit | 38 pass | | | | |
| 1.7 | vinu-portfolio unit | 10 pass | | | | |
| 1.8 | vinu-agent unit | 88 pass | | | | |
| 1.9 | vinu-live unit | 14 pass | | | | |
| 1.10 | vinu-infra unit | 12 pass | | | | |
| 2.1 | Block 1 — data (candles × 1D/4H/1H) | rows > 0, OHLC non-zero | AAPL 128/303/930 rows all non-zero; TSLA pending retry (contention) | PASS (AAPL) / PENDING (TSLA) | evidence/block1-data.md | |
| 2.2 | Block 2 — features (parquet) | rows > 0, indicators non-null | AAPL 128/303/930 rows, parquet written; TSLA 4H/1H failed (stock-api contention), 1D timeout | PASS (AAPL) / PENDING (TSLA) | evidence/block2-features.md | |
| 2.3 | Block 3 — analysis (angles, evaluate, backtest) | all outputs present | AAPL angles 281/281 runs, 31/31; evaluate 31.41s weight +0.25; backtest Sharpe 0.538, 8 trades | PASS (AAPL) / IN PROGRESS (TSLA) | evidence/03-analysis/ | see block3-analysis.md |
| 2.4 | Block 4 — portfolio (build + evaluate) | success | state 6 strategies, daily-allocation + regime, risk-status PASS | PASS | evidence/04-portfolio/ | see block4-portfolio.md |
| 2.5 | Block 5 — agent/live (session, shadow eval) | success | session ok (degraded LLM 429); shadow-evaluate ok 0 artifacts | PASS W/ DEV | evidence/05-agent-live/ | see block5-agent-live.md |
| 3.1 | run_pipeline.py AAPL | completes, artifacts written | stock 47.49s ok; news FAILED (19,503 LLM calls, 19,417×429); analysis completed server-side | PARTIAL | evidence/06-research/pipeline-aapl-news-fail.json | free-tier 429 flood |
| 3.2 | run_pipeline.py TSLA | completes, artifacts written | analysis in progress server-side (19/281 runs at last check) | IN PROGRESS | | ~1h30m fresh run |
| 3.3 | portfolio e2e integration test | pass | not run this session | PENDING | | |
| 3.4 | live shadow evaluator real endpoint | pass | ran (0 artifacts — none approved) | PARTIAL | | needs approved artifact |
| 3.5 | agent e2e/integration tests | pass | session round-trip ok (LLM degraded) | PARTIAL | | free-tier 429 |
| 3.6 | research LLM run (OpenRouter) | run completes w/ artifact | 76.73s, 1 iteration, strategy code generated, validation STOP | PASS W/ DEV | evidence/06-research/research-aapl-run3.json | all gemma calls 429, degraded |
| 4.1 | Gap 1 — research approve unreachable | REPRODUCED | | | | |
| 4.2 | Gap 2 — order pending_confirmation dead-end | REPRODUCED | | | | |
| 4.3 | Gap 3 — strategy registry drift | REPRODUCED | | | | |
| 4.4 | Gap 4 — fallback URLs missing prefix | REPRODUCED | | | | |
| 4.5 | Gap 5 — simulator run_id discarded | REPRODUCED | | | | |
