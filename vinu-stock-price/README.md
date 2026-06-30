# vinu-stock-price

Historical and live **1m OHLCV** storage in **Parquet** (archive + live), with a small **meta.db** catalog, pluggable providers (Polygon, Alpaca, Yahoo), and HTTP/CLI query API.

Sibling to [vinu-news](../vinu-news/).

## Documentation

- [Complete architecture guide](docs/complete_guide_stock_price.md) — repo layout, providers, flows, API, Docker
- [How to use](how-to/README.md) — install, backfill, live ingest, CLI/API examples

## Quick start

```bash
cd vinu-stock-price
cp .env.example .env
pip install -e ".[dev]"

# Add symbols
vinu-stock-query watchlist AAPL NVDA

# Backfill history (uses providers.yaml priority; needs API keys or Yahoo fallback)
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024

# Live append (watchlist)
vinu-stock-ingest --once

# Query
vinu-stock-query candles AAPL --interval 5m --days 7

# API
vinu-stock-serve
# http://127.0.0.1:8081/docs
# http://127.0.0.1:8081/ui
```

## Web UI

After `vinu-stock-serve` or `docker compose up`, open:

```
http://localhost:8081/ui
```

Three tabs:

- **Settings** — poll interval, default provider, watchlist, ingest/backfill triggers
- **Coverage** — symbol catalog health (bar ranges, backfill status)
- **Prices** — candle table, sparkline, and candlestick chart

## Data layout

```
data/
├── meta.db
└── prices/1m/{SYMBOL}/
    ├── archive/{YYYY}.parquet
    └── live/{YYYY}.parquet
```

Only **1m** bars are stored. Request `interval=5m` (or 1h, 1d) on the API/CLI to aggregate at read time.

## Providers

Edit [`vinu_stock/providers/config/providers.yaml`](vinu_stock/providers/config/providers.yaml) to reorder or disable providers.

| Provider | Env vars | Roles |
|----------|----------|-------|
| polygon | `POLYGON_API_KEY` | backfill, live |
| alpaca | `ALPACA_API_KEY`, `ALPACA_API_SECRET` | live, backfill |
| yahoo | (none) | fallback |

## Docker

```bash
docker compose up --build
```

Manual backfill inside container:

```bash
docker compose run --rm api vinu-stock-backfill AAPL --from-year 2023
```

## HTTP API

| Endpoint | Description |
|----------|-------------|
| `GET /candles/{symbol}` | `interval`, `from`, `to`, `days`, `provider` |
| `GET /catalog` | Symbol coverage |
| `POST /backfill/trigger` | Backfill watchlist |
| `POST /ingest/trigger` | One live cycle |
| `/watchlist/tickers` | Same pattern as vinu-news |

## Tests

```bash
pytest tests/ -v
```
