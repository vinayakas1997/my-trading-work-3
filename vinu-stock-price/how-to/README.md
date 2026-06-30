# How to Use vinu-stock-price

Practical guide: install, backfill history, run live ingest, and query OHLCV data.

Architecture details: [Complete Guide](../docs/complete_guide_stock_price.md)

---

## Prerequisites

- Python **3.10+**
- Optional API keys for deeper history and reliable live data:
  - [Polygon](https://polygon.io/) — `POLYGON_API_KEY`
  - [Alpaca](https://alpaca.markets/) — `ALPACA_API_KEY`, `ALPACA_API_SECRET`
- Without keys, **Yahoo** is used as fallback (limited 1m depth; fine for testing)

---

## Install

```bash
cd vinu-stock-price
cp .env.example .env
pip install -e ".[dev]"
```

Verify CLI:

```bash
vinu-stock-query catalog
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VINU_STOCK_DATA_ROOT` | `./data` | Parquet tree root |
| `VINU_STOCK_META_DB_PATH` | `./data/meta.db` | Catalog + watchlist SQLite |
| `VINU_STOCK_POLL_INTERVAL_SEC` | `60` | Live ingest interval |
| `VINU_STOCK_HOST` | `127.0.0.1` | API bind host |
| `VINU_STOCK_PORT` | `8081` | API port |
| `VINU_STOCK_DEFAULT_PROVIDER` | `polygon` | Settings default |
| `POLYGON_API_KEY` | — | Polygon.io |
| `ALPACA_API_KEY` | — | Alpaca data |
| `ALPACA_API_SECRET` | — | Alpaca data |
| `ALPACA_DATA_BASE_URL` | `https://data.alpaca.markets` | Alpaca data endpoint |

---

## First-run workflow

### 1. Add symbols to the watchlist

**CLI:**

```bash
vinu-stock-query watchlist AAPL NVDA
```

**HTTP** (with API running):

```bash
curl -X POST http://localhost:8081/watchlist/tickers \
  -H "Content-Type: application/json" \
  -d '{"tickers":["AAPL","NVDA"]}'
```

### 2. Backfill historical 1m bars

Backfill writes **archive** Parquet files (`data/prices/1m/{SYMBOL}/archive/{YEAR}.parquet`).

**One symbol, one year (good first test):**

```bash
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
```

**Auto-discover earliest year through last complete year:**

```bash
vinu-stock-backfill AAPL
```

**All watchlist symbols:**

```bash
vinu-stock-backfill
```

### 3. Run live ingest (append new 1m bars)

**Once:**

```bash
vinu-stock-ingest --once
```

**Continuous (every 60s by default):**

```bash
vinu-stock-ingest --continuous
# or explicit interval:
vinu-stock-ingest --interval 120
```

### 4. Query candles

**CLI — 1m, last 7 days:**

```bash
vinu-stock-query candles AAPL --interval 1m --days 7 --limit 500
```

**CLI — 5m aggregated from stored 1m:**

```bash
vinu-stock-query candles AAPL --interval 5m --days 30
```

**HTTP:**

```bash
curl "http://localhost:8081/candles/AAPL?interval=5m&days=7"
```

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `vinu-stock-backfill [SYMBOL...]` | Historical year jobs → archive Parquet |
| `vinu-stock-ingest --once` | One live append cycle |
| `vinu-stock-ingest --continuous` | Poll watchlist on interval |
| `vinu-stock-serve` | Start HTTP API on port 8081 |
| `vinu-stock-query candles SYMBOL` | Print JSON candles |
| `vinu-stock-query catalog` | List symbol catalog |
| `vinu-stock-query watchlist TICKER...` | Add tickers |

**Backfill options:**

```bash
vinu-stock-backfill AAPL --from-year 2020 --to-year 2024 --verbose
vinu-stock-backfill --data-root ./mydata --meta-db ./mydata/meta.db
```

---

## HTTP API examples

Start server:

```bash
vinu-stock-serve
# Open http://127.0.0.1:8081/docs
```

## Web UI

After `vinu-stock-serve` or `docker compose up`:

```
http://localhost:8081/ui
```

Workflow: **Coverage** tab to verify backfill ranges → **Prices** tab to load candles (table + chart). **Settings** for watchlist and manual ingest/backfill.

## HTTP API examples (curl)

| Action | curl |
|--------|------|
| Health | `curl http://localhost:8081/health` |
| Catalog | `curl http://localhost:8081/catalog` |
| Symbol catalog | `curl http://localhost:8081/catalog/AAPL` |
| Candles | `curl "http://localhost:8081/candles/AAPL?interval=1m&days=3"` |
| Time range | `curl "http://localhost:8081/candles/AAPL?from=1700000000&to=1700100000"` |
| Watchlist | `curl http://localhost:8081/watchlist/tickers` |
| Settings | `curl http://localhost:8081/settings` |
| Trigger backfill | `curl -X POST http://localhost:8081/backfill/trigger` |
| Trigger ingest | `curl -X POST http://localhost:8081/ingest/trigger` |

**Query parameters for `/candles/{symbol}`:**

- `interval` — `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`
- `days` — rolling window (default-friendly for recent data)
- `from` / `to` — UTC epoch seconds
- `provider` — filter by `polygon`, `alpaca`, `yahoo`
- `limit` — max rows (default 5000)

---

## Docker

```bash
cd vinu-stock-price
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8081
- Live ingest runs automatically in `live-ingest` service

**Manual backfill in container:**

```bash
docker compose run --rm api vinu-stock-backfill AAPL --from-year 2023 --to-year 2024
```

Data persists in Docker volume `vinu_stock_data`.

---

## Provider order

Edit [`vinu_stock/providers/config/providers.yaml`](../vinu_stock/providers/config/providers.yaml):

```yaml
providers:
  - id: polygon
    priority: 1
    roles: [backfill, live]
  - id: alpaca
    priority: 2
    roles: [live, backfill]
  - id: yahoo
    priority: 99
    roles: [fallback]
```

Lower `priority` = tried first. Restart ingest/API after changes (registry loads at process start).

---

## Data on disk

```
data/
├── meta.db                    # symbol_catalog, backfill_jobs, watchlist
└── prices/1m/AAPL/
    ├── archive/2024.parquet   # frozen historical years
    └── live/2026.parquet      # appended live 1m bars
```

**Inspect with DuckDB (optional):**

```bash
duckdb -c "SELECT * FROM read_parquet('data/prices/1m/AAPL/archive/*.parquet') LIMIT 5"
```

---

## Tests

```bash
cd vinu-stock-price
pytest tests/ -v
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `count: 0` on `/candles` | No Parquet for symbol | Run `vinu-stock-backfill` first |
| `count: 0` with `days=7` | Bars older than window | Use `from`/`to` epoch range or recent backfill |
| Backfill fails all years | No API keys | Set Polygon/Alpaca keys or rely on Yahoo fallback |
| `POLYGON_API_KEY not set` | Provider not configured | Add key to `.env` or lower Yahoo priority for testing |
| Live ingest adds 0 bars | Market closed or no new closed minutes | Normal off-hours; check `ingest_log` in meta.db |
| Port conflict | vinu-news on 8080 | vinu-stock uses **8081** |

---

## Typical daily workflow

1. Ensure watchlist has your symbols (`vinu-stock-query watchlist` or API).
2. Run backfill once for new symbols (or `POST /backfill/trigger`).
3. Keep `vinu-stock-ingest --continuous` or Docker `live-ingest` running.
4. Query via CLI or HTTP for charts, backtests, or join with [vinu-news](../../vinu-news/) on `(ticker, time)`.
