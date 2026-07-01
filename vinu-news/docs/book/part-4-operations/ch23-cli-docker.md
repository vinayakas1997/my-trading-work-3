# Chapter 23 — CLI & Docker

| Field | Value |
|-------|-------|
| **Package** | vinu-news |
| **Module** | `vinu_news/cli.py`, `docker-compose.yml`, `Dockerfile` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Ch 01, Ch 22 |

## Learning objectives

- Run the three CLI entry points: `vinu-news-ingest`, `vinu-news-serve`, `vinu-news-query`.
- Deploy with Docker Compose (ingest + api services sharing one volume).
- Override DB path and feed subset from the command line.

## 1. Problem this module solves

Operators need both **local Python** workflows (two terminals: ingest + serve) and **containerized** deployments where ingest polls automatically and API serves on `:8080`. Entry points are registered in `pyproject.toml` and implemented in `cli.py`; Docker Compose wires them with shared persistent storage.

## 2. Position in pipeline

```mermaid
flowchart TD
  subgraph docker [docker compose]
    Ingest[vinu-news-ingest --continuous]
    API[vinu-news-serve :8080]
  end
  Vol[vinu_data volume] --> Ingest
  Vol --> API
  Ingest --> DB[/data/news.db]
  API --> DB
```

| Step | Input | Output |
|------|-------|--------|
| Ingest CLI | RSS + pipeline | DB writes + terminal report |
| Serve CLI | HTTP requests | JSON API + `/ui` |
| Query CLI | Subcommand | JSON stdout |
| Docker | `.env` + compose | Two long-running services |

## 3. File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Console script entry points |
| `vinu_news/cli.py` | `ingest_main`, `serve_main`, `query_main` |
| `vinu_news/server/app.py` | `serve_main` uses `create_app()` |
| `docker-compose.yml` | `ingest` + `api` services |
| `Dockerfile` | Image build for both services |
| `.env.example` | Env template for compose |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `--once` / `--continuous` / `--interval` | flag/int | ingest mode | `--once` |
| `--feeds` | string | no | `federal_reserve,ap_top_news` |
| `--dry-run` | flag | no | fetch only |
| `--db` | path | no | overrides `VINU_NEWS_DB_PATH` |
| `--host`, `--port` | serve | no | API bind |

### Output

| Field | Type | Example |
|-------|------|---------|
| Ingest report | text | `IngestionSummary.format_report()` |
| Query JSON | stdout | Article list |
| Docker logs | text | Per-service poll output |

## 5. Logic (step by step)

### vinu-news-ingest

1. Parse `--once`, `--continuous`, or `--interval SECONDS`.
2. Optional `--feeds` comma list → `load_feeds(feed_ids)`.
3. `--continuous` uses env default interval for first sleep; then reads **DB** `poll_interval_sec` each cycle.
4. Calls `NewsService.run_ingestion_cycle()` with mode filter.
5. Prints formatted summary.

### vinu-news-serve

1. Loads config from `.env`.
2. Creates FastAPI app via `create_app()`.
3. Runs uvicorn on `VINU_NEWS_HOST` / `VINU_NEWS_PORT`.

### vinu-news-query

Subcommands: `latest`, `ticker`, `search`, `settings`, `watchlist`.

### Docker Compose

- **ingest:** `vinu-news-ingest --continuous`, DB at `/data/news.db`
- **api:** `vinu-news-serve --host 0.0.0.0 --port 8080`, same volume
- Shared `vinu_data` volume persists mode, watchlist, articles

**Docker users:** use curl or `/docs` — do not run ingest on host separately.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `VINU_NEWS_DB_PATH` | env | `./data/news.db` | Local CLI path |
| Docker override | compose | `/data/news.db` | Container DB |
| `VINU_NEWS_POLL_INTERVAL_SEC` | env | `600` | Initial poll seed |
| `poll_interval_sec` | DB | from env | Continuous ingest sleep |
| `--verbose` | CLI | off | DEBUG logging |

## 7. Worked examples

### Example A — happy path (local two-terminal)

Terminal 1:

```bash
cd vinu-news
pip install -e ".[dev]"
cp .env.example .env
vinu-news-ingest --continuous
```

Terminal 2:

```bash
vinu-news-serve
# Open http://127.0.0.1:8080/docs and http://127.0.0.1:8080/ui
```

Query:

```bash
vinu-news-query latest --limit 10
vinu-news-query ticker NVDA --days 7
vinu-news-query search "Fed rates"
vinu-news-query watchlist add AAPL NVDA
vinu-news-query settings set mode all
```

### Example B — edge case (Docker fresh volume, ticker mode)

```bash
docker compose up --build
curl http://localhost:8080/latest
# count may be 0 until watchlist + trigger

curl -X POST http://localhost:8080/watchlist/tickers \
  -H "Content-Type: application/json" \
  -d '{"tickers":["AAPL"]}'

curl -X POST http://localhost:8080/ingest/trigger
```

Poll interval change via API applies on **next** ingest sleep — no container restart.

```bash
curl -X PATCH http://localhost:8080/settings \
  -H "Content-Type: application/json" \
  -d '{"poll_interval_sec":300}'
```

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| CLI | `vinu-news-ingest --once` | `--feeds`, `--dry-run`, `--db` | Terminal report |
| CLI | `vinu-news-ingest --interval 900` | seconds | Poll loop |
| CLI | `vinu-news-serve` | `--host`, `--port`, `--db` | HTTP server |
| CLI | `vinu-news-query settings show` | — | mode + interval JSON |
| CLI | `vinu-news-query watchlist show` | — | tickers JSON |
| Docker | `docker compose up --build` | — | ingest + api |
| Docker | `docker compose logs ingest` | — | Poll history |

Legacy module entry (still valid):

```bash
python -m vinu_news.rss.run_ingestion --once --verbose
```

## 9. SQL / queries (if applicable)

Confirm Docker volume DB:

```bash
docker compose exec api sqlite3 /data/news.db "SELECT COUNT(*) FROM articles;"
```

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_service.py` | Ingest cycle via service |
| `rss/tests/test_ingestion_pipeline.py` | Pipeline CLI path |
| `pytest tests/ -v` | Full suite |

## 11. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Ingest not writing | Ticker mode, empty watchlist | Add tickers or `mode=all` |
| API empty, ingest OK | Different `--db` paths | Align paths; Docker uses shared volume |
| Interval not changing | Read from DB each cycle | PATCH settings; wait one sleep |
| Port 8080 in use | Conflict | Change `VINU_NEWS_PORT` |
| Windows DB locked | Open handle | Close service before delete |
| Compose rebuild slow | Image cache | `docker compose build --no-cache` only if needed |

## 12. Fincept / reference repo mapping

| Fincept reference | CLI/Docker |
|-------------------|------------|
| Ingestion loop | `vinu-news-ingest --continuous` |
| Query interface | `vinu-news-query` + HTTP API |
| Production deploy | Docker Compose pattern |

## 13. Related chapters

- [Chapter 01 — Install & First Run](../part-0-getting-started/ch01-install-first-run.md)
- [Chapter 06 — Ingestion Orchestration](../part-1-ingestion/ch06-ingestion-orchestration.md)
- [Chapter 22 — HTTP API](ch22-http-api.md)
- [Chapter 24 — Config & Environment](ch24-config-env.md)
