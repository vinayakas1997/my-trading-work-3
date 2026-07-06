# Chapter 05 — Price API client

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/clients/price_client.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch03 |

## 1. File map

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_candles(symbol, from_ts, to_ts, limit)` | `GET /candles/{symbol}` | Fetch OHLCV candle data |

## 2. Data contract

Each candle contains:

| Field | Type | Example |
|-------|------|---------|
| `bar_ts` | int | `1712345678` |
| `open` | float | `150.25` |
| `high` | float | `152.00` |
| `low` | float | `149.80` |
| `close` | float | `151.50` |
| `volume` | int | `1000000` |

## 3. Logic

Returns up to 5000 candles per call. The caller (engine modules) is responsible for filtering to the needed time range. Uses the same `net.request()` Docker-aware HTTP helper.
