# Chapter 26 — Config & env vars

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/config.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch01 |

## 1. Configuration class

`VinuCorrelationConfig` is a frozen dataclass loaded from environment variables via `load_config()`.

## 2. Env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `VINU_CORRELATION_DATA_ROOT` | `./data` | Data directory root |
| `VINU_NEWS_API_URL` | `http://127.0.0.1:8080` | News API base URL |
| `VINU_STOCK_API_URL` | `http://127.0.0.1:8081` | Stock price API base URL |
| `VINU_CORRELATION_HOST` | `127.0.0.1` | HTTP server bind address |
| `VINU_CORRELATION_PORT` | `8083` | HTTP server port |
| `VINU_CORRELATION_IMPACT_HIGH_THRESHOLD` | `2.0` | High impact price change % |
| `VINU_CORRELATION_IMPACT_MEDIUM_THRESHOLD` | `0.5` | Medium impact price change % |
| `VINU_CORRELATION_DRAWDOWN_MIN_PCT` | `-3.0` | Drawdown detection threshold % |
| `VINU_CORRELATION_DRAWDOWN_LOOKBACK_HOURS` | `24` | Drawdown lookback window |
| `VINU_CORRELATION_BASELINE_WINDOW_DAYS` | `7` | Baseline rolling window |
| `VINU_CORRELATION_MARKET_HOURS_ONLY` | `true` | Filter to market hours |
| `VINU_CORRELATION_SESSION_BREAK_ON_CLOSE` | `true` | Clamp windows at session boundaries |
| `VINU_CORRELATION_CACHE_MAXSIZE` | `128` | LRU cache max entries |
| `VINU_CORRELATION_CACHE_TTL_SEC` | `300` | Cache TTL (5 min) |
| `VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC` | `3600` | Continuous loop interval |
| `VINU_CORRELATION_COMPACT_THRESHOLD` | `50` | Row group count before compaction |

## 3. Load order

1. `.env` in the package root directory
2. `.env` in the current working directory
3. System environment variables (override `.env`)
