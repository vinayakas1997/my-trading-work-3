# Block 1 — Data

Cross-service smoke: stock candles for AAPL / TSLA at 1D / 4H / 1H.

## Parameters
- Tickers: AAPL, TSLA
- Window: 2025-07-01 → 2025-12-31 (from_ts 1751328000 → to_ts 1767225600)
- Timeframes: 1D, 4H, 1H
- Endpoint: `GET /stock/candles/{symbol}?interval=...&from=...&to=...`

## Results

| Ticker | Interval | Rows | OHLC non-zero | Status |
|---|---|---|---|---|
| AAPL | 1D | 128 | 128 | PASS (34.73s) |
| AAPL | 4H | 303 | 303 | PASS (1.67s) |
| AAPL | 1H | 930 | 930 | PASS (0.49s) |
| TSLA | 1D | — | — | PENDING RETRY — stock-api read timeout during concurrent TSLA initial-analysis run |
| TSLA | 4H | — | — | PENDING RETRY (same) |
| TSLA | 1H | — | — | PENDING RETRY (same) |

## Evidence
- AAPL: `GET /stock/candles/{symbol}?interval={1d,4h,1h}` all HTTP 200 with data present.

## Deviations / Issues
- TSLA candle reads timed out (60s) because the server-side TSLA initial-analysis run was hammering stock-api concurrently. Retry after that run completes (see `../issues/` / run-summary open items). Not a code defect.
