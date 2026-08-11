# Block 1 — Data

Cross-service smoke: stock candles for AAPL / TSLA at 1D / 4H / 1H.

## Parameters
- Tickers: AAPL, TSLA
- Window: 2025-07-01 → 2025-12-31
- Timeframes: 1D, 4H, 1H
- Endpoint: `GET /stock/candles/{symbol}?interval=...&from=1751328000&to=1767225600`

## Results

| Ticker | Interval | Rows | OHLC non-zero | Status |
|---|---|---|---|---|
| AAPL | 1D | | | |
| AAPL | 4H | | | |
| AAPL | 1H | | | |
| TSLA | 1D | | | |
| TSLA | 4H | | | |
| TSLA | 1H | | | |

## Evidence
- `evidence/block1-data/` (raw responses)

## Deviations / Issues
- (link to deviations/issues if any)
