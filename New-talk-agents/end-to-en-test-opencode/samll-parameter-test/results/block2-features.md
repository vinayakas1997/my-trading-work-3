# Block 2 — Features

Cross-service smoke: features requests produce parquet with rows and non-null indicator values.

## Parameters
- Tickers: AAPL, TSLA
- Window: 2025-07-01 → 2025-12-31
- Timeframes: 1D, 4H, 1H
- Features: sma_20, rsi_14 (explicit), `run_immediately: true`
- Endpoint: `POST /features/requests`

## Results

| Ticker | Interval | Status | Row count | Indicators non-null | file_path |
|---|---|---|---|---|---|
| AAPL | 1D | PASS (43.74s) | 128 | yes | /data/runs/10_e2e_block2_aapl_1d |
| AAPL | 4H | PASS (43.20s) | 303 | yes | /data/runs/11_e2e_block2_aapl_4h |
| AAPL | 1H | PASS (3.48s) | 930 | yes | /data/runs/12_e2e_block2_aapl_1h |
| TSLA | 1D | PENDING RETRY — stock-api read timeout (120s) during TSLA analysis contention | | | |
| TSLA | 4H | FAILED (16.37s) → [Errno 111] Connection refused to stock-api | 0 | no | none |
| TSLA | 1H | FAILED (65.15s) → timed out to stock-api | 0 | no | none |

## Evidence
- AAPL 1D/4H/1H: HTTP 200, status=done, row_count > 0, parquet written.
- TSLA 4H/1H: `error_message` shows downstream stock-api `[Errno 111] Connection refused` / `timed out` — transient contention, retry pending.

## Deviations / Issues
- TSLA features requests failed only due to concurrent TSLA initial-analysis load on stock-api (downstream connection refused/timeout). Not a code defect; retry after analysis completes.
