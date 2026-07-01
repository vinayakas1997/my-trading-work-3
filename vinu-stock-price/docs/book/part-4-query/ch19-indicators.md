# Chapter 19 — Technical Indicators

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | `vinu_stock/query/indicators.py` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 17, Chapter 18 |

## Learning objectives

- List all names in `SUPPORTED_INDICATORS` and request them via API/CLI.
- Understand compute-at-read semantics and warm-up `None` values.
- Order indicators after aggregation and optional adjustment in `fetch_candles`.

## 1. Problem this module solves

Researchers want **RSI, MACD, SMA**, and simple return stats without a separate indicator database. **TASK-S01** computes indicators in Python after DuckDB loads OHLC rows — keeping Parquet schema stable while allowing comma-separated indicator names on `/candles` and CLI.

## 2. Position in pipeline

```mermaid
flowchart LR
  DUCK[DuckDB 1m rows] --> AGG[aggregate_bars]
  AGG --> ADJ[apply_adjusted_prices?]
  ADJ --> IND[apply_indicators]
  IND --> JSON[API response]
```

| Step | Input | Output |
|------|-------|--------|
| `parse_indicator_names` | `"rsi_14,sma_20"` | Validated list or `ValueError` |
| `apply_indicators` | rows + names | Rows with extra float columns |
| Warm-up | first N bars | `null` for insufficient history |

## 3. File map

| File | Responsibility |
|------|----------------|
| `query/indicators.py` | `SUPPORTED_INDICATORS`, SMA/RSI/MACD/return/vol |
| `query/engine.py` | Calls `apply_indicators` when `indicators` set |
| `service.py` | `get_candles(..., indicators=...)` |
| `server/routes_read.py` | `indicators` query param |
| `cli.py` | `--indicators` on candles subcommand |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `indicators` | string | no | `rsi_14,macd,sma_20` |
| `rows` | list[dict] | yes | Must include `close` float |
| `interval` | string | no | Indicators run on **post-aggregate** closes |

### Output

| Field | Type | Example |
|-------|------|---------|
| `sma_5` … `sma_50` | float \| null | `182.34` |
| `rsi_14` | float \| null | `55.2` |
| `macd` | float \| null | Line from EMA12−EMA26 |
| `macd_signal` | float \| null | 9-period EMA of MACD |
| `daily_return` | float \| null | `(close-prev)/prev` per bar |
| `volatility_20d` | float \| null | Rolling std of daily_return, 20 bars |

### `SUPPORTED_INDICATORS` (complete list)

| Name | Algorithm | First valid index (typical) |
|------|-----------|----------------------------|
| `sma_5` | 5-bar simple moving average of close | index 4 |
| `sma_10` | 10-bar SMA | index 9 |
| `sma_20` | 20-bar SMA | index 19 |
| `sma_50` | 50-bar SMA | index 49 |
| `rsi_14` | Wilder-style RSI, period 14 | index 14 |
| `macd` | EMA(12) − EMA(26) on close | index 25 |
| `macd_signal` | EMA(9) of MACD line | index 33 |
| `daily_return` | Bar-over-bar return on close | index 1 |
| `volatility_20d` | Population std of `daily_return`, window 20 | index 20 |

## 5. Logic (step by step)

1. **`parse_indicator_names`** — split on comma, lower-case, reject unknown via `SUPPORTED_INDICATORS`.
2. **`apply_indicators`** — copy rows; extract `closes` list.
3. For each requested name:
   - `sma_N` — `_sma(closes, N)` sliding window.
   - `rsi_14` — `_rsi(closes, 14)` with smoothed avg gain/loss.
   - `macd` / `macd_signal` — `_macd`: EMA12, EMA26, signal EMA9; null padding before warm-up indices.
   - `daily_return` — `_daily_return` on closes.
   - `volatility_20d` — `_rolling_std` of daily returns, period 20.
4. **`fetch_candles`** order: DuckDB → `aggregate_bars` → `apply_adjusted_prices` (if `adjusted`) → `apply_indicators`.
5. Requesting both `macd` and `macd_signal` in one call computes MACD once internally when each name is processed (duplicate EMA work — acceptable for v1).

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `indicators` | API query | none | Comma-separated names |
| `--indicators` | CLI | none | Same |
| `limit` | API | `5000` | Max bars — affects indicator warm-up |

## 7. Worked examples

### Example A — happy path (RSI + SMA via API)

```bash
curl "http://127.0.0.1:8081/candles/AAPL?interval=5m&days=30&indicators=rsi_14,sma_20"
```

Last rows include `rsi_14` and `sma_20` when enough 5m bars exist.

### Example B — edge case (unknown indicator)

```bash
curl "http://127.0.0.1:8081/candles/AAPL?indicators=bollinger"
# HTTP 400 — ValueError: Unknown indicators: bollinger
```

### Example C — CLI

```bash
vinu-stock-query candles AAPL --interval 1d --days 90 --indicators macd,macd_signal,daily_return
```

### Example D — Python unit pattern

```python
from vinu_stock.query.indicators import apply_indicators, parse_indicator_names

names = parse_indicator_names("rsi_14,sma_20")
rows = [{"close": 100.0 + i * 0.5} for i in range(30)]
out = apply_indicators(rows, names)
assert out[-1]["sma_20"] is not None
```

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| GET | `/candles/{symbol}` | `indicators=rsi_14,sma_20` | Extra JSON fields per bar |
| — | `vinu-stock-query candles` | `--indicators` | JSON array |
| `StockService.get_candles` | Python | `indicators=["rsi_14"]` | list[dict] |

## 9. SQL / queries (if applicable)

Indicators are **not** in SQL — computed in Python after DuckDB fetch. For raw OHLC only:

```sql
SELECT bar_ts, close
FROM read_parquet('data/prices/1m/AAPL/live/*.parquet')
ORDER BY bar_ts DESC
LIMIT 100;
```

Pass result to `apply_indicators` in a notebook if needed.

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_indicators.py` | `parse_indicator_names`, SMA+RSI, adjusted prices |
| `tests/test_api.py` | Candles route (base); add indicator integration locally |

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| All indicator fields `null` | `limit` too small vs period | Increase `limit` or `days` |
| MACD null on 1m 1-day window | Warm-up needs 34+ bars | Widen window |
| Different RSI vs TradingView | Algorithm variant | v1 uses simplified Wilder loop |
| Indicators on wrong scale | `adjusted=false` with splits | Use `adjusted=true` |

## 12. Fincept / reference repo mapping

| vinu-stock-price | Reference |
|------------------|-----------|
| Query-time TA | Fincept chart overlays (computed not stored) |
| TASK-S01 | enhancement-doc1 indicators deliverable |
| No TA-Lib dependency | Pure Python for CI simplicity |

## 13. Related chapters

- [Chapter 17 — Query Engine](ch17-query-engine.md)
- [Chapter 18 — Aggregation](ch18-aggregation.md)
- [Chapter 12 — Adjusted Close](../part-2-storage/ch12-adjusted-close.md)
- [Chapter 21 — HTTP API](../part-5-operations/ch21-http-api.md)
