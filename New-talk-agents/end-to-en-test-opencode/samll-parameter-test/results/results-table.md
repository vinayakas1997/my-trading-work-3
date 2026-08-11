# Results Table (Master Matrix)

Service / block × expected × actual × status.

| # | Service / Block | Expected | Actual | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| 0.1 | agent-api up | healthy | | | | |
| 0.2 | live-api up | healthy | | | | |
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
| 2.1 | Block 1 — data (candles × 1D/4H/1H) | rows > 0, OHLC non-zero | | | | |
| 2.2 | Block 2 — features (parquet) | rows > 0, indicators non-null | | | | |
| 2.3 | Block 3 — analysis (angles, evaluate, backtest) | all outputs present | | | | |
| 2.4 | Block 4 — portfolio (build + evaluate) | success | | | | |
| 2.5 | Block 5 — agent/live (session, shadow eval) | success | | | | |
| 3.1 | run_pipeline.py AAPL | completes, artifacts written | | | | |
| 3.2 | run_pipeline.py TSLA | completes, artifacts written | | | | |
| 3.3 | portfolio e2e integration test | pass | | | | |
| 3.4 | live shadow evaluator real endpoint | pass | | | | |
| 3.5 | agent e2e/integration tests | pass | | | | |
| 4.1 | Gap 1 — research approve unreachable | REPRODUCED | | | | |
| 4.2 | Gap 2 — order pending_confirmation dead-end | REPRODUCED | | | | |
| 4.3 | Gap 3 — strategy registry drift | REPRODUCED | | | | |
| 4.4 | Gap 4 — fallback URLs missing prefix | REPRODUCED | | | | |
| 4.5 | Gap 5 — simulator run_id discarded | REPRODUCED | | | | |
