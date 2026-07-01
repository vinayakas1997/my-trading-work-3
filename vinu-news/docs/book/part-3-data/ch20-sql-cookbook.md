# Chapter 20 — SQL Cookbook

| Field | Value |
|-------|-------|
| **Package** | vinu-news |
| **Module** | `vinu_news/analysis/storage/repository.py` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Ch 17, Ch 18 |

## Learning objectives

- Run copy-paste SQL playbooks for story lifecycle, ticker intensity, and source quality.
- Use FTS5 `MATCH` syntax for macro narrative research.
- Combine Python `NewsRepository` helpers with raw SQL for deeper analysis.

## 1. Problem this module solves

Analysts need repeatable queries against `news.db` without re-deriving joins and UTC date filters each time. This cookbook collects proven patterns from production research workflows: active threads, ticker daily stats, high-impact filters, feed health, and FTS phrase search.

## 2. Position in pipeline

```mermaid
flowchart LR
  DB[(news.db)] --> SQL[Cookbook queries]
  SQL --> Research[Notebooks / reports]
  Repo[NewsRepository] --> DB
```

| Step | Input | Output |
|------|-------|--------|
| Ingest | RSS + pipeline | Populated tables |
| Query | SQL or repository | Research datasets |

## 3. File map

| File | Responsibility |
|------|----------------|
| `storage/repository.py` | Python query helpers |
| `storage/schema.sql` | Table/column reference |
| `storage/fts.py` | FTS5 virtual table |
| `docs/news_derived_tables.md` | Legacy playbook source |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `ticker` | TEXT | per query | `'AAPL'` |
| `thread_id` | TEXT | per query | SHA256 string |
| FTS query | string | search | `'Powell AND rates'` |
| UTC date | TEXT | rollups | `'2026-06-29'` |

### Output

| Field | Type | Example |
|-------|------|---------|
| Article rows | result set | headline, sentiment, sort_ts |
| Thread metrics | result set | days_active, article_count |
| Daily rollups | result set | bull_ratio, article_count |

## 5. Logic (step by step)

1. All `sort_ts` values are Unix seconds UTC.
2. Snapshot `date` columns are `YYYY-MM-DD` UTC derived from `sort_ts`.
3. FTS uses `articles_fts MATCH` with Porter + unicode61 tokenizer.
4. Prefer repository helpers for parameterized access; use SQL for ad-hoc research.
5. Join externally for OHLCV — not stored in this database.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `VINU_NEWS_DB_PATH` | env | `./data/news.db` | Query target file |
| FTS tokenizer | `fts.py` | `porter unicode61` | Search behavior |

## 7. Worked examples

### Example A — happy path (story lifecycle)

**Goal:** Find hot ongoing stories in the last 7 days.

```sql
SELECT
    thread_id,
    lead_headline,
    dominant_ticker,
    article_count,
    datetime(first_seen_at, 'unixepoch') AS first_seen,
    datetime(last_seen_at, 'unixepoch') AS last_seen,
    (last_seen_at - first_seen_at) / 86400.0 AS days_active
FROM story_threads
WHERE last_seen_at >= strftime('%s', 'now', '-7 days')
ORDER BY article_count DESC;
```

```python
import time
from vinu_news.analysis.storage.repository import NewsRepository

since = int(time.time()) - 7 * 86400
with NewsRepository() as repo:
    threads = repo.get_active_threads(since)
    for t in threads[:5]:
        timeline = repo.get_thread_timeline(t["thread_id"])
        print(t["lead_headline"], timeline)
```

### Example B — edge case (ticker intensity spike)

**Goal:** Detect abnormal AAPL coverage vs prior 30 days.

```sql
SELECT
    date,
    article_count,
    bullish_count,
    bearish_count,
    ROUND(bullish_count * 1.0 / NULLIF(article_count, 0), 2) AS bull_ratio
FROM ticker_daily_stats
WHERE ticker = 'AAPL'
  AND date >= date('now', '-30 days')
ORDER BY date;
```

Compare latest `article_count` to rolling average manually or in a notebook.

## 8. API / CLI (if applicable)

HTTP endpoints mirror many cookbook patterns:

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| GET | `/search` | `q` | FTS via repository |
| GET | `/high-impact` | `hours`, `sentiment` | HIGH impact filter |
| GET | `/stats/ticker/{symbol}` | `days` | Daily stats |
| GET | `/threads/active` | `hours` | Active threads |
| CLI | `vinu-news-query search "Powell rates"` | — | FTS JSON |

## 9. SQL / queries (if applicable)

### Articles for one UTC day

```sql
SELECT headline, source, sentiment, impact
FROM articles
WHERE sort_ts >= strftime('%s', '2026-06-29')
  AND sort_ts <  strftime('%s', '2026-06-30')
ORDER BY sort_ts DESC;
```

### HIGH impact bullish (last 24h)

```sql
SELECT headline, source, datetime(sort_ts, 'unixepoch') AS pub
FROM articles
WHERE impact = 'HIGH' AND sentiment = 'BULLISH'
  AND sort_ts >= strftime('%s', 'now', '-1 day')
ORDER BY sort_ts DESC;
```

### Peak day for a thread

```sql
SELECT date, article_count, bullish_count, bearish_count
FROM thread_daily_snapshots
WHERE thread_id = ?
ORDER BY article_count DESC
LIMIT 1;
```

### FTS phrase search

```sql
SELECT a.headline, a.source
FROM articles a
JOIN articles_fts ON a.rowid = articles_fts.rowid
WHERE articles_fts MATCH '"Federal Reserve" AND rates'
ORDER BY rank
LIMIT 20;
```

### Source quality (feed health)

```sql
SELECT feed_id, fail_streak, total_failures, total_polls,
       ROUND(avg_latency_ms, 0) AS avg_ms, last_error
FROM feed_health
WHERE fail_streak > 0 OR total_failures > 0
ORDER BY fail_streak DESC, total_failures DESC;
```

### Macro narrative (Powell / rates)

```python
with NewsRepository() as repo:
    hits = repo.search_articles("Powell AND rates")
    thread_ids = {h["thread_id"] for h in hits if h["thread_id"]}
    for tid in thread_ids:
        print(repo.get_thread(tid))
        print(repo.get_thread_timeline(tid))
```

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `analysis/tests/test_fts.py` | MATCH queries |
| `analysis/tests/test_persist.py` | Rollup counts |
| `analysis/tests/test_enrichment.py` | Repository helpers |

## 11. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| FTS returns nothing | Empty DB or bad syntax | Run ingest; use AND/OR/quotes |
| Date boundary off-by-one | Local vs UTC | Use `strftime` UTC boundaries |
| Snapshot > article count | Thread matches | Expected (Ch 18) |
| `top_thread_id` misleading | Last write wins | Not highest volume thread |
| No price correlation | No OHLCV in DB | Join vinu-stock-price externally |

## 12. Fincept / reference repo mapping

| Fincept reference | Cookbook section |
|-------------------|------------------|
| Derived tables research | Playbooks A–E |
| FTS5 §7 | Phrase search query |
| Feed monitoring | feed_health query |

## 13. Related chapters

- [Chapter 17 — Schema Catalog](ch17-schema-catalog.md)
- [Chapter 18 — articles & threads](ch18-table-articles-threads.md)
- [Chapter 14 — Story Threads & Persist](../part-2-analysis/ch14-story-threads-persist.md)
- [Chapter 22 — HTTP API](../part-4-operations/ch22-http-api.md)
