# Appendix B — Troubleshooting Guide

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | — |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 01 |

## Learning objectives

- Diagnose common failures across providers, ingest, catalog, and query.
- Use `ingest_log`, `backfill_jobs`, and `/health` as first-line tools.
- Know which chapter deep-dives each subsystem.

## 1. Problem this module solves

Operators hit recurring issues: empty candles, API key errors, zero-bar ingest cycles, DuckDB path mistakes. This appendix consolidates **symptom → cause → fix** tables from across the textbook into one lookup, organized by subsystem.

## 2. Position in pipeline

```mermaid
flowchart TD
  H[/health] --> P[Providers OK?]
  P -->|no| KEYS[Fix .env keys]
  P -->|yes| CAT[Catalog coverage?]
  CAT -->|no| BF[Backfill]
  CAT -->|yes| ING[ingest_log]
  ING --> QRY[Query paths]
```

| Step | Input | Output |
|------|-------|--------|
| `/health` | running server | data_root, provider configured flags |
| `ingest_log` | SQLite | Per-symbol live errors |
| `backfill_jobs` | SQLite | Failed year jobs |

## 3. File map

| File | Responsibility |
|------|----------------|
| `data/meta.db` | catalog, jobs, ingest_log, watchlist |
| `.env` | API keys, paths |
| `ingest_log` table | Live cycle audit |
| `backfill_jobs` table | Historical job errors |

## 4. Data contracts

### Diagnostic queries (inputs)

| Field | Type | Example |
|-------|------|---------|
| `symbol` | TEXT | `AAPL` |
| `ingest_log.ok` | int | `0` = failure |
| `backfill_jobs.status` | TEXT | `failed` |
| `gap_count` | int | >0 warnings |

### Healthy signals (outputs)

| Signal | Meaning |
|--------|---------|
| `backfill_status=complete` | All years processed |
| `bars_added>0` on open market | Live path working |
| `/candles` returns rows | Query + Parquet OK |

## 5. Logic (step by step)

**Triage order:**

1. `curl http://127.0.0.1:8081/health` — verify data root and providers.
2. `curl http://127.0.0.1:8081/catalog/AAPL` — `first_bar_ts`, `last_bar_ts`, `gap_count`.
3. `sqlite3 data/meta.db "SELECT * FROM backfill_jobs WHERE status='failed'"`.
4. `sqlite3 data/meta.db "SELECT * FROM ingest_log ORDER BY id DESC LIMIT 20"`.
5. Verify Parquet exists: `ls data/prices/1m/AAPL/archive/`.
6. Test query: `vinu-stock-query candles AAPL --days 1`.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `POLYGON_API_KEY` | env | — | Primary provider |
| `VINU_STOCK_DATA_ROOT` | env | `./data` | Wrong path → empty queries |
| `VINU_STOCK_META_DB_PATH` | env | `{data_root}/meta.db` | Stale catalog if duplicated |

## 7. Worked examples

### Example A — happy path (recover from empty candles)

```bash
vinu-stock-query watchlist AAPL
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
vinu-stock-query candles AAPL --days 1
```

### Example B — edge case (all providers fail)

```bash
vinu-stock-backfill XYZ --from-year 2024 --to-year 2024 --verbose
sqlite3 data/meta.db "SELECT error FROM backfill_jobs WHERE symbol='XYZ'"
```

Expect chained errors from registry; Yahoo may still work for valid liquid symbols without keys.

### Example C — live ingest silent

```bash
vinu-stock-ingest --once --verbose
sqlite3 data/meta.db "SELECT symbol, bars_added, ok, error FROM ingest_log ORDER BY id DESC LIMIT 5"
```

Off-hours `bars_added=0` with `ok=1` is normal ([ch14](../part-3-ingest/ch14-live-ingest.md)).

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| GET | `/health` | — | Diagnostics |
| GET | `/catalog/{symbol}` | — | Coverage |
| POST | `/backfill/trigger` | — | Re-run backfill |
| POST | `/ingest/trigger` | — | One live cycle |
| — | `pytest tests/ -v` | — | Verify install |

## 9. SQL / queries (if applicable)

```sql
-- Failed backfill jobs
SELECT symbol, year, status, error FROM backfill_jobs WHERE status = 'failed';

-- Live failures
SELECT symbol, error, datetime(run_at, 'unixepoch')
FROM ingest_log WHERE ok = 0 ORDER BY id DESC;

-- Stale symbols (last bar > 1 day old during market week)
SELECT symbol, datetime(last_bar_ts, 'unixepoch') AS last_bar
FROM symbol_catalog
WHERE last_bar_ts < strftime('%s', 'now') - 86400;
```

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_api.py` | Health, candles smoke |
| `tests/test_providers_mock.py` | Fallback chain |
| Full suite | `pytest tests/ -v` |

## 11. Troubleshooting

### Providers

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `polygon: not configured` | Missing key | `POLYGON_API_KEY` in `.env` |
| All providers fail | Bad symbol / range | Verify ticker; try recent dates |
| Yahoo empty 1m | Range too long / throttle | Narrow window; retry |

### Ingest

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `bars_added: 0` always | Market closed | Normal; check during RTH |
| `symbols_failed` > 0 | Provider error | `ingest_log.error` |
| Stale `last_bar_ts` | Ingest not running | `--continuous` or Docker |

### Query

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Empty JSON array | No Parquet / wrong root | Backfill; check `data_root` in settings |
| Wrong interval | Aggregation misunderstanding | See [ch18](../part-4-query/ch18-aggregation.md) |
| `Unknown indicators` | Typo | [ch19](../part-4-query/ch19-indicators.md) list |

### Docker

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Empty volume | Fresh container | Run backfill inside container |
| Port conflict | 8081 in use | Change `VINU_STOCK_PORT` |

## 12. Fincept / reference repo mapping

| vinu-stock-price | Reference |
|------------------|-----------|
| ingest_log | vinu-news ingestion audit |
| Provider fallback | Multi-broker degradation pattern |
| `/health` | Service readiness probe |

## 13. Related chapters

- [Chapter 01 — Install](../part-0-getting-started/ch01-install-first-run.md)
- [Chapter 16 — Retry & Gaps](../part-3-ingest/ch16-retry-gap-validation.md)
- [Chapter 26 — Config](../part-5-operations/ch26-config-env.md)
- [Appendix C — Test Map](apx-c-test-map.md)
