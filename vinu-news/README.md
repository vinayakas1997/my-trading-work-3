# vinu-news

Installable financial news ingestion service with a runtime settings bridge, watchlist-driven collection, SQLite storage (Postgres planned v1.1), and HTTP API.

## First run

1. Copy env template:

```bash
cd vinu-news
cp .env.example .env
```

2. **Docker** (recommended — ingest + API start automatically):

```bash
docker compose up --build
```

3. Add tickers and poll immediately (fresh DB starts in **`ticker`** mode — nothing saved until you do this):

```bash
curl -X POST http://localhost:8080/watchlist/tickers \
  -H "Content-Type: application/json" \
  -d '{"tickers":["AAPL","NVDA"]}'

curl -X POST http://localhost:8080/ingest/trigger
```

4. When you want **all** news (not just watchlist), switch mode:

```bash
curl -X PATCH http://localhost:8080/settings \
  -H "Content-Type: application/json" \
  -d '{"mode":"all"}'
```

**Docker users:** use **curl** (or http://localhost:8080/docs). You do not run `vinu-news-ingest` on your host — the ingest container polls every 10 minutes automatically.

**Local Python users:** after `pip install` and copying `.env`, no `--db` flag needed:

```bash
vinu-news-ingest --once
vinu-news-ingest --continuous
vinu-news-serve
```

## Package layout

```
vinu_news/
  analysis/     # enrichment, storage, threads
  rss/          # RSS fetch and parse
  server/       # HTTP API
  collection/   # ticker-mode persist filter
  settings/     # runtime mode bridge
  watchlist/
```

## Install

From the `vinu-news` directory:

```bash
pip install -e ".[dev]"
```

## Quick start (local)

Terminal 1 — ingest worker:

```bash
vinu-news-ingest --once
# or continuous (uses VINU_NEWS_POLL_INTERVAL_SEC from .env, default 600):
vinu-news-ingest --continuous
# or explicit interval:
vinu-news-ingest --interval 600
```

Terminal 2 — HTTP API:

```bash
vinu-news-serve
```

Open interactive docs: http://127.0.0.1:8080/docs

## Environment

Copy [`.env.example`](.env.example) to `.env`. Variables are loaded automatically.

| Variable | Default | Description |
|----------|---------|-------------|
| `VINU_NEWS_STORAGE` | `sqlite` | `sqlite` or `postgres` (postgres stub in v1) |
| `VINU_NEWS_DB_PATH` | `./data/news.db` | SQLite file path |
| `VINU_NEWS_DATABASE_URL` | — | Postgres URL (v1.1) |
| `VINU_NEWS_MODE` | `ticker` | Initial mode when DB is first created |
| `VINU_NEWS_POLL_INTERVAL_SEC` | `600` | Default poll interval (10 min) |
| `VINU_NEWS_HOST` | `127.0.0.1` | API bind host |
| `VINU_NEWS_PORT` | `8080` | API bind port |

**Note:** Mode is stored in the DB after first run. Existing Docker volumes keep their saved mode — use `PATCH /settings` or delete the volume to reset.

## Settings bridge (change anytime)

```bash
# HTTP
curl http://localhost:8080/settings
curl -X PATCH http://localhost:8080/settings -H "Content-Type: application/json" -d '{"mode":"all"}'

# CLI
vinu-news-query settings set mode all
```

Modes:

- **`ticker`** (default) — save only articles mentioning a watchlist ticker
- **`all`** — save every lead article from RSS

Mode is read at the **start of each ingest cycle**; no restart required.

## Watchlist

```bash
curl -X POST http://localhost:8080/watchlist/tickers \
  -H "Content-Type: application/json" \
  -d '{"tickers":["AAPL","NVDA"]}'

curl http://localhost:8080/watchlist/tickers
curl -X DELETE http://localhost:8080/watchlist/tickers/AAPL
```

Trigger an immediate poll after adding tickers:

```bash
curl -X POST http://localhost:8080/ingest/trigger
```

## Consume data (no input required)

```bash
curl http://localhost:8080/latest
curl http://localhost:8080/high-impact
curl http://localhost:8080/threads/active
```

## Consume by ticker

```bash
curl http://localhost:8080/ticker/NVDA
curl http://localhost:8080/ticker/NVDA?days=3&limit=10
curl http://localhost:8080/watchlist/news
curl http://localhost:8080/search?q=Powell+inflation
curl http://localhost:8080/stats/ticker/NVDA?days=7
curl "http://localhost:8080/articles/since?ts=1719667200"
```

## CLI query

```bash
vinu-news-query latest --limit 10
vinu-news-query ticker NVDA --days 7
vinu-news-query search "Fed rates"
vinu-news-query watchlist add AAPL NVDA
```

## Docker

```bash
cd vinu-news
cp .env.example .env
docker compose up --build
```

Services:

- **ingest** — polls every 600s into shared volume (`VINU_NEWS_MODE=ticker` from `.env`)
- **api** — HTTP on port 8080

## Production notes

- Add API key auth and rate limiting before exposing publicly
- Postgres support is stubbed for v1.1 (`VINU_NEWS_STORAGE=postgres`)
- Switching `all` → `ticker` does not delete existing rows; switching back to `all` resumes full persist

## Tests

```bash
pytest tests/ -v
```
