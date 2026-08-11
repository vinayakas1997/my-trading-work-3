# Block 2 — Features

Cross-service smoke: features requests produce parquet with rows and non-null indicator values.

## Parameters
- Tickers: AAPL, TSLA
- Window: 2025-07-01 → 2025-12-31
- Timeframes: 1D, 4H, 1H
- Features: preset `basic_ta` (or explicit sma_20 / rsi_14)
- Endpoint: `POST /features/requests`

## Results

| Ticker | Interval | Status | Row count | Indicators non-null | file_path |
|---|---|---|---|---|---|
| AAPL | 1D | | | | |
| AAPL | 4H | | | | |
| AAPL | 1H | | | | |
| TSLA | 1D | | | | |
| TSLA | 4H | | | | |
| TSLA | 1H | | | | |

## Evidence
- `evidence/block2-features/` (request payloads, response JSON, parquet row sample)

## Deviations / Issues
- (link to deviations/issues if any)
