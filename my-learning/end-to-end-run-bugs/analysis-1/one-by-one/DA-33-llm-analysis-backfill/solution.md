# DA-33 🟠 LLM Analysis Has No Backfill for Unanalyzed Articles

**Component:** `vinu-news`
**Files Changed:**
- `vinu-news/vinu_news/service.py`
- `vinu-news/vinu_news/server/schemas.py`
- `vinu-news/vinu_news/server/routes_config.py`
- `vinu-news/vinu_news/cli.py`

## Problem

LLM analysis can be toggled on/off via `VINU_LLM_ANALYSIS_MODE` env var or `PATCH /settings`. When set to `manual`, articles are ingested but not sent to the LLM for analysis. When switched back to `auto`, the background worker (`AutoAnalysisWorker`) only processes **newly inserted articles** — any articles ingested while analysis was off are silently skipped. There is no way to catch up.

## Root Cause

The `AutoAnalysisWorker` uses a queue that starts empty at worker initialization. After each ingestion cycle, `_maybe_auto_analyze()` is called with only the current cycle's `inserted_links`. There is no query for articles that exist in the `articles` table but have no corresponding row in `news_analysis`. The `news_analysis` table (keyed by URL) already tracks which articles have been analyzed — but the code never checks it for backfill purposes.

## Solution

### 1. `AutoAnalysisWorker.backfill_unanalyzed()` (service.py)

Added a new method that queries for articles missing LLM analysis and submits them to the existing queue:

```sql
SELECT a.link FROM articles a
LEFT JOIN news_analysis n ON a.link = n.url
WHERE n.url IS NULL
ORDER BY a.sort_ts DESC
LIMIT ?
```

### 2. Auto-backfill on startup (service.py:__init__)

After creating the `AutoAnalysisWorker` on service startup with mode `auto`, calls `backfill_unanalyzed()` automatically.

### 3. Auto-backfill on mode toggle (service.py:patch_settings)

When `PATCH /settings` switches mode from `manual` to `auto`, calls `backfill_unanalyzed()` after creating the worker.

### 4. Public `NewsService.backfill_analysis()` method (service.py)

Exposes the backfill via the service layer for API and CLI access.

### 5. `POST /news/analyze/backfill` endpoint (routes_config.py)

Accepts `{"limit": 500}` body, returns `{"submitted": N}`. Allows manual triggering from any HTTP client.

### 6. `AnalysisBackfillRequest` model (schemas.py)

Pydantic model with `limit: int = Field(default=500, ge=1, le=5000)`.

### 7. CLI `backfill-analysis` subcommand (cli.py)

`vinu-news query backfill-analysis --limit 1000` triggers the backfill from the command line.

## Local LLM Safety

For users running local LLMs (Ollama, llama.cpp, etc.), these env vars are recommended:

```env
VINU_LLM_ANALYSIS_CONCURRENCY=1     # 1 request at a time
VINU_LLM_RATE_LIMIT=5               # 5 requests/min
```

The backfill respects these settings automatically — it just adds links to the queue, and workers process at whatever rate the LLM can handle.

## Verification

1. **Auto mode start:** Start the service with `VINU_LLM_ANALYSIS_MODE=auto`. If there are unanalyzed articles, logs show: `Backfill: submitted N / M unanalyzed articles`

2. **Mode toggle:** Start with `manual`, ingest some articles, then `PATCH /settings {"llm_analysis_mode": "auto"}`. Check logs for backfill message.

3. **API:** `curl -X POST http://localhost:8000/news/analyze/backfill -H 'Content-Type: application/json' -d '{"limit": 10}'`

4. **CLI:** `vinu-news query backfill-analysis --limit 10`

5. **SQL check before/after:**
   ```sql
   SELECT COUNT(*) FROM articles a
   LEFT JOIN news_analysis n ON a.link = n.url
   WHERE n.url IS NULL;
   ```
