# Enhancement Plan 1: vinu-complete-manager — Unified System Dashboard

## Objective

Build a central `vinu-complete-manager` module that aggregates health, status, and trace data from all 6 vinu components into a single tab-based SPA dashboard at `http://localhost:8086`, giving full system transparency — every operation visible, every call traceable.

---

## Architecture Overview

```
vinu-complete-manager (port 8086)
├── GET / → SPA Dashboard (React, 10 tabs)
├── GET /api/status               → aggregated health of all 6 components
├── GET /api/status/{component}   → detailed status for one component
├── GET /api/llm/traces           → LLM call traces (proxied from news)
├── GET /api/backfill/detail      → per-ticker backfill granularity (proxied from news)
├── GET /api/enrichment/{id}      → enrichment trace per article (proxied from news)
├── GET /api/api-traces           → outbound API call log (proxied from news)
└── GET /api/proxy/{comp}/{path:path}  → transparent pass-through to any component
```

All services are accessible via Docker DNS:

| Component | Internal hostname | Port | Exposed |
|-----------|-------------------|:----:|:-------:|
| vinu-news | `news-api` | 8080 | `localhost:8080` |
| vinu-stock-price | `stock-api` | 8081 | `localhost:8081` |
| vinu-features | `features-api` | 8082 | `localhost:8082` |
| vinu-correlation | `correlation-api` | 8083 | `localhost:8083` |
| vinu-strategy | `strategy-api` | 8084 | `localhost:8084` |
| vinu-simulator | `simulator-api` | 8085 | `localhost:8085` |
| **vinu-complete-manager** | `complete-manager` | 8086 | **`localhost:8086`** |

---

## 1. New Module: `vinu-complete-manager/`

### File structure

```
vinu-complete-manager/
├── .env.example
├── Dockerfile
├── pyproject.toml
├── vinu_complete_manager/
│   ├── __init__.py
│   ├── cli.py                   # CLI entry point
│   ├── config.py                # CompleteManagerConfig from env
│   ├── net.py                   # Async HTTP client (httpx, retry, timeout)
│   ├── checker.py               # Polls all 6 components, aggregates status
│   └── server/
│       ├── app.py               # FastAPI app + static mount + startup
│       ├── routes.py            # All /api/* endpoints
│       └── schemas.py           # AggregatedStatus, ComponentStatus, etc.
└── web/                         # React SPA (served by app.py as static/)
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx              # Tab container + auto-refresh (every 5s)
        ├── api.js               # fetch wrapper for /api/*
        ├── components/
        │   ├── TabBar.jsx
        │   ├── OverviewTab.jsx
        │   ├── BackfillTab.jsx
        │   ├── LlmTracesTab.jsx
        │   ├── EnrichmentTab.jsx
        │   ├── ApiCallsTab.jsx
        │   ├── CorrelationTab.jsx
        │   ├── StrategyTab.jsx
        │   ├── StockTab.jsx
        │   ├── FeaturesTab.jsx
        │   ├── SimulatorTab.jsx
        │   └── AdvancedTable.jsx
```

### `config.py`

```python
@dataclass
class CompleteManagerConfig:
    news_api_url: str        # default http://news-api:8080
    stock_api_url: str       # default http://stock-api:8081
    features_api_url: str    # default http://features-api:8082
    correlation_api_url: str # default http://correlation-api:8083
    strategy_api_url: str    # default http://strategy-api:8084
    simulator_api_url: str   # default http://simulator-api:8085
    poll_interval_sec: int   # default 30 (background cache refresh)
    host: str                # default 0.0.0.0
    port: int                # default 8086
```

### `net.py`

Async httpx client with:
- 5s timeout per component
- 2 retries with exponential backoff
- Graceful degradation (down component → status=error, not crash)

### `checker.py`

Background background task (runs every `poll_interval_sec`):
- Calls `GET /health` on all 6 components in parallel
- Calls `GET /backfill/status` on news
- Calls `GET /runs?limit=1` on simulator
- Caches aggregated result in-memory (thread-safe dict)
- Frontend reads cache instantly per request

### `schemas.py`

```python
class ComponentStatus(BaseModel):
    name: str
    status: str          # "ok" | "degraded" | "error" | "unknown"
    health: dict | None
    error: str | None
    latency_ms: int | None
    updated_at: datetime

class AggregatedStatus(BaseModel):
    pipeline_status: str  # "healthy" | "degraded" | "down"
    components: dict[str, ComponentStatus]
    summary: str          # "6/6 online" etc.
    generated_at: datetime
```

### `routes.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Aggregated status of all 6 components |
| `/api/status/{component}` | GET | Detailed status for one component |
| `/api/llm/traces` | GET | Proxied from vinu-news `/llm/traces` |
| `/api/backfill/detail` | GET | Proxied from vinu-news `/backfill/detail` |
| `/api/enrichment/{article_id}` | GET | Proxied from vinu-news `/enrichment/{article_id}` |
| `/api/api-traces` | GET | Proxied from vinu-news `/api-traces` |
| `/api/proxy/{component}/{path:path}` | GET | Generic pass-through to any component |
| `/` | GET | Serves React SPA (`static/index.html`) |

---

## 2. Frontend: React SPA (served by manager)

### Dashboard Tabs

| Tab | Source | Content |
|-----|--------|---------|
| **📊 Overview** | `/api/status` | 6 component cards (name, green/yellow/red badge, key metrics, latency). Pipeline health banner at top. |
| **📰 Backfill** | `/api/backfill/detail` | Per-ticker table: ticker, status, enabled, backfilled_up_to, oldest_ts, article_count, error. Sortable by each column. |
| **🤖 LLM Traces** | `/api/llm/traces` | Table: timestamp, ticker, model, prompt (truncated), response (truncated), tokens, duration_ms. Click row → full detail modal. |
| **🔍 Enrichment** | `/api/enrichment/{id}` | Per-article: financial lexicon matches found, VADER scores (compound/pos/neg/neu), LLM classification, sentiment label. Search by article_id or ticker. |
| **📞 API Calls** | `/api/api-traces` | Table: timestamp, component, method, url, status_code, duration_ms, ticker, error. Filter by component (Alpaca/Yahoo/FMP/LLM). |
| **🔗 Correlation** | Proxy to correlation API | Ticker selector → show impact events, correlation coefficient, granger causality, drawdowns. Three sub-views. |
| **📈 Strategy** | Proxy to strategy API | Active strategies list, current weights per ticker, rule traces, evaluation runs. |
| **💹 Stock** | Proxy to stock API | Symbol catalog table (ticker, first bar, last bar, bar count), provider status per ticker. |
| **📐 Features** | Proxy to features API | Indicator catalog table, request queue status (pending/running/completed), per-request detail. |
| **🎮 Simulator** | Proxy to simulator API | Runs table, click → run detail page (metrics, equity curve, trades list). |

### `AdvancedTable.jsx`

Reusable component with:
- **Column definition** config (label, accessor, sortable, filterable, width)
- **Sort**: click column header to toggle asc/desc
- **Filter**: text input per column (case-insensitive substring match)
- **Pagination**: 25/50/100 per page
- **Auto-refresh**: component re-fetches data on parent's refresh tick

### Auto-refresh

- `App.jsx` sets a `setInterval(fetchAll, 5000)` — every 5 seconds
- Each tab subscribes to the refresh tick and re-fetches its data if visible
- User can pause auto-refresh with a toggle button
- `App.jsx` tracks active tab, only re-fetches data for the visible tab to reduce load

---

## 3. Modifications to Existing Components

### 3.1 vinu-news — LLM Tracing

**New table in `schema.sql`:**

```sql
CREATE TABLE IF NOT EXISTS llm_trace (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id        TEXT,
    ticker            TEXT,
    model             TEXT NOT NULL,
    prompt            TEXT NOT NULL,
    response          TEXT NOT NULL,
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens      INTEGER DEFAULT 0,
    duration_ms       INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'ok',
    error_message     TEXT,
    created_at        INTEGER NOT NULL
);
```

**New table for API call tracing:**

```sql
CREATE TABLE IF NOT EXISTS api_call_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    component         TEXT NOT NULL,   -- 'alpaca', 'yahoo', 'fmp', 'llm'
    method            TEXT NOT NULL,   -- 'GET', 'POST'
    url               TEXT NOT NULL,
    status_code       INTEGER,
    duration_ms       INTEGER DEFAULT 0,
    ticker            TEXT,
    error             TEXT,
    created_at        INTEGER NOT NULL
);
```

**Init in `sqlite_backend.py`**: Run `CREATE TABLE IF NOT EXISTS` during setup.

**LLM logging hook** in `vinu_news/analysis/enrichment/llm.py`:
- Wrap `_call_llm()` or equivalent function
- Before call: record start time, model, prompt
- After call: record response, tokens, duration, status
- Insert into `llm_trace` table
- Do NOT block the main flow (fire-and-forget insert)

**API call logging hook**:
- Create a wrapper httpx session in `vinu_news/http.py`
- Every `GET`/`POST` through this session logs to `api_call_log`
- Wrap provider HTTP calls in `AlpacaTickerNewsProvider`, `YahooProvider`, `FMPProvider`

**New routes in `vinu_news/server/routes_read.py`:**

| Endpoint | Description |
|----------|-------------|
| `GET /llm/traces` | List LLM traces (filter by ticker, model, date range; paginated) |
| `GET /llm/traces/{id}` | Single trace detail |
| `GET /enrichment/{article_id}` | Enrichment detail for one article (lexicon matches, VADER scores, LLM result) |
| `GET /api-traces` | List API call logs (filter by component, status_code, ticker; paginated) |
| `GET /backfill/detail` | Per-ticker backfill detail including resume timestamp, oldest article |

**Enrichment trace data** (stored alongside the article or computable on read):
- `financial_lexicon_matches`: list of matched phrases + scores
- `vader_scores`: compound, pos, neg, neu
- `llm_classification`: bullish/bearish/neutral if LLM was run
- `llm_confidence`: if available

These are already computed during enrichment — just need an endpoint to expose them per article.

### 3.2 vinu-strategy — Add `/health`

**In `vinu_strategy/server/app.py` or new `routes.py`:**

```python
@router.get("/health")
async def health():
    return {
        "ok": True,
        "strategies_count": len(strategies),
        "active_strategies": [s.name for s in strategies if s.enabled],
        "weights_count": db.count_weights(),
        "runs_count": db.count_runs(),
        "data_root": config.data_root,
    }
```

### 3.3 vinu-correlation — Enrich `/health`

Current: `{"ok": True}`

Target:
```python
@router.get("/health")
async def health():
    return {
        "ok": True,
        "db_path": config.db_path,
        "event_count": db.count_impact_events(),
        "tickers_count": db.count_tracked_tickers(),
        "news_api_url": config.news_api_url,
        "stock_api_url": config.stock_api_url,
    }
```

### 3.4 vinu-simulator — Enrich `/health`

Current: `{"ok": True}`

Target:
```python
@router.get("/health")
async def health():
    return {
        "ok": True,
        "run_count": db.count_runs(),
        "total_trades": db.total_trades(),
        "last_run_at": db.last_run_timestamp(),
        "strategy_api_url": config.strategy_api_url,
        "stock_api_url": config.stock_api_url,
    }
```

---

## 4. Docker Compose Addition

Add to `docker-compose.yml`:

```yaml
  # =========================================================================
  # vinu-complete-manager Service (Ports: 8086)
  # =========================================================================
  complete-manager:
    build:
      context: ./vinu-complete-manager
      dockerfile: Dockerfile
    command: ["uvicorn", "vinu_complete_manager.server.app:app", "--host", "0.0.0.0", "--port", "8086"]
    ports:
      - "8086:8086"
    environment:
      NEWS_API_URL: http://news-api:8080
      STOCK_API_URL: http://stock-api:8081
      FEATURES_API_URL: http://features-api:8082
      CORRELATION_API_URL: http://correlation-api:8083
      STRATEGY_API_URL: http://strategy-api:8084
      SIMULATOR_API_URL: http://simulator-api:8085
    restart: unless-stopped
    depends_on:
      - news-api
      - stock-api
      - features-api
      - correlation-api
      - strategy-api
      - simulator-api
```

---

## 5. Implementation Order

### Phase 1 — Manager skeleton + Overview tab (MVP)
| Step | File(s) | What |
|------|---------|------|
| 1 | `vinu-complete-manager/pyproject.toml`, `Dockerfile`, `.env.example` | Module scaffold |
| 2 | `vinu-complete-manager/vinu_complete_manager/config.py` | Config from env |
| 3 | `vinu-complete-manager/vinu_complete_manager/net.py` | Async HTTP client |
| 4 | `vinu-complete-manager/vinu_complete_manager/checker.py` | Aggregated status poller |
| 5 | `vinu-complete-manager/vinu_complete_manager/server/schemas.py` | Pydantic models |
| 6 | `vinu-complete-manager/vinu_complete_manager/server/app.py` | FastAPI app + routes skeleton |
| 7 | `vinu-complete-manager/vinu_complete_manager/server/routes.py` | `/api/status`, `/api/status/{comp}`, `/api/proxy/{comp}/{path}` |
| 8 | React scaffold + `OverviewTab.jsx` | 6 component cards |
| 9 | Modify `docker-compose.yml` | Add manager service |

### Phase 2 — vinu-news tracing tables + endpoints
| Step | File(s) | What |
|------|---------|------|
| 10 | `vinu-news/vinu_news/storage/schema.sql` | Add `llm_trace` + `api_call_log` tables |
| 11 | `vinu-news/vinu_news/storage/sqlite_backend.py` | Init new tables, add insert/query methods |
| 12 | `vinu-news/vinu_news/http.py` (new) | Wrapped httpx session with logging |
| 13 | `vinu-news/vinu_news/analysis/enrichment/llm.py` | Wrap `_call_llm` with trace logging |
| 14 | `vinu-news/vinu_news/server/routes_read.py` | Add `/llm/traces`, `/enrichment/{id}`, `/api-traces`, `/backfill/detail` |
| 15 | Wire provider HTTP calls to use wrapped session | Alpaca, Yahoo, FMP providers |

### Phase 3 — Remaining component health enrichment
| Step | File(s) | What |
|------|---------|------|
| 16 | `vinu-strategy/vinu_strategy/server/app.py` | Add `/health` route |
| 17 | `vinu-correlation/vinu_correlation/server/routes_read.py` | Enrich `/health` |
| 18 | `vinu-simulator/vinu_simulator/server/app.py` | Enrich `/health` |

### Phase 4 — Full SPA with all tabs
| Step | File(s) | What |
|------|---------|------|
| 19 | `BackfillTab.jsx` | Per-ticker table |
| 20 | `LlmTracesTab.jsx` | LLM trace table + detail modal |
| 21 | `EnrichmentTab.jsx` | Enrichment viewer |
| 22 | `ApiCallsTab.jsx` | API call log table |
| 23 | `CorrelationTab.jsx` | Ticker selector + impact/corr/drawdown |
| 24 | `StrategyTab.jsx` | Strategies + weights + traces |
| 25 | `StockTab.jsx` | Catalog + coverage |
| 26 | `FeaturesTab.jsx` | Indicators + requests |
| 27 | `SimulatorTab.jsx` | Runs + metrics + trades |

### Phase 5 — Polish
| Step | What |
|------|------|
| 28 | Auto-refresh with pause toggle |
| 29 | Error handling UI (component down → red badge + error message) |
| 30 | `npm run build` → copy to `vinu_complete_manager/server/static/` |
| 31 | Test full stack |

---

## API Response Schemas

### `GET /api/status`

```json
{
  "pipeline_status": "healthy",
  "summary": "6/6 components online",
  "components": {
    "vinu-news": {
      "name": "vinu-news",
      "status": "ok",
      "health": {
        "article_count": 12345,
        "mode": "ticker",
        "watchlist_count": 7,
        "llm_active": true
      },
      "latency_ms": 12,
      "updated_at": "2026-07-07T12:00:00Z"
    },
    "vinu-stock": {
      "name": "vinu-stock",
      "status": "ok",
      "health": {
        "symbol_count": 7,
        "providers": [
          {"id": "yfinance", "enabled": true, "configured": true},
          {"id": "polygon", "enabled": false, "configured": false}
        ]
      },
      "latency_ms": 8,
      "updated_at": "2026-07-07T12:00:00Z"
    },
    "vinu-features": {
      "name": "vinu-features",
      "status": "ok",
      "health": {
        "catalog_count": 48,
        "presets_count": 3,
        "pending_requests": 0,
        "running_requests": 1
      },
      "latency_ms": 15,
      "updated_at": "2026-07-07T12:00:00Z"
    },
    "vinu-correlation": {
      "name": "vinu-correlation",
      "status": "ok",
      "health": {
        "event_count": 247,
        "tickers_count": 7
      },
      "latency_ms": 5,
      "updated_at": "2026-07-07T12:00:00Z"
    },
    "vinu-strategy": {
      "name": "vinu-strategy",
      "status": "ok",
      "health": {
        "strategies_count": 3,
        "active_strategies": ["momentum", "mean-reversion"],
        "weights_count": 42
      },
      "latency_ms": 10,
      "updated_at": "2026-07-07T12:00:00Z"
    },
    "vinu-simulator": {
      "name": "vinu-simulator",
      "status": "ok",
      "health": {
        "run_count": 15,
        "total_trades": 340,
        "last_run_at": "2026-07-06T18:30:00Z"
      },
      "latency_ms": 7,
      "updated_at": "2026-07-07T12:00:00Z"
    }
  },
  "generated_at": "2026-07-07T12:00:01Z"
}
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dashboard serving | Single SPA at port 8086 | Everything at one URL, one auth boundary |
| Auto-refresh | 5s interval, per-tab | Responsive but not wasteful (visible tab only) |
| Data grid | Custom `AdvancedTable.jsx` (no AG Grid) | Lighter weight, no license cost, full control |
| LLM tracing | Async insert, non-blocking | Never slow down the main article pipeline |
| API call tracing | Wrapped httpx session | Single point of instrumentation, no code changes per provider |
| Error handling | Graceful degradation | One down component doesn't crash the dashboard |
| Proxy routes | Generic `/api/proxy/{comp}/{path}` | No need to hardcode every endpoint — frontend can fetch anything |
| Backend caching | In-memory, polled every 30s | Fast frontend reads, no thundering herd on 6 components |

---

## Files to Create

| # | File | Phase |
|---|------|:-----:|
| 1 | `vinu-complete-manager/pyproject.toml` | 1 |
| 2 | `vinu-complete-manager/Dockerfile` | 1 |
| 3 | `vinu-complete-manager/.env.example` | 1 |
| 4 | `vinu-complete-manager/vinu_complete_manager/__init__.py` | 1 |
| 5 | `vinu-complete-manager/vinu_complete_manager/cli.py` | 1 |
| 6 | `vinu-complete-manager/vinu_complete_manager/config.py` | 1 |
| 7 | `vinu-complete-manager/vinu_complete_manager/net.py` | 1 |
| 8 | `vinu-complete-manager/vinu_complete_manager/checker.py` | 1 |
| 9 | `vinu-complete-manager/vinu_complete_manager/server/__init__.py` | 1 |
| 10 | `vinu-complete-manager/vinu_complete_manager/server/app.py` | 1 |
| 11 | `vinu-complete-manager/vinu_complete_manager/server/routes.py` | 1 |
| 12 | `vinu-complete-manager/vinu_complete_manager/server/schemas.py` | 1 |
| 13 | `vinu-complete-manager/web/package.json` | 1 |
| 14 | `vinu-complete-manager/web/vite.config.js` | 1 |
| 15 | `vinu-complete-manager/web/src/main.jsx` | 1 |
| 16 | `vinu-complete-manager/web/src/App.jsx` | 1 |
| 17 | `vinu-complete-manager/web/src/api.js` | 1 |
| 18 | `vinu-complete-manager/web/src/components/TabBar.jsx` | 1 |
| 19 | `vinu-complete-manager/web/src/components/OverviewTab.jsx` | 1 |
| 20 | `vinu-complete-manager/web/src/components/AdvancedTable.jsx` | 1 |
| 21 | `vinu-news/vinu_news/http.py` | 2 |
| 22 | `vinu-news/vinu_news/storage/schema.sql` (modify) | 2 |
| 23 | `vinu-news/vinu_news/storage/sqlite_backend.py` (modify) | 2 |
| 24 | `vinu-news/vinu_news/analysis/enrichment/llm.py` (modify) | 2 |
| 25 | `vinu-news/vinu_news/server/routes_read.py` (modify) | 2 |
| 26 | `vinu-strategy/vinu_strategy/server/app.py` (modify) | 3 |
| 27 | `vinu-correlation/vinu_correlation/server/routes_read.py` (modify) | 3 |
| 28 | `vinu-simulator/vinu_simulator/server/app.py` (modify) | 3 |
| 29 | `vinu-complete-manager/web/src/components/BackfillTab.jsx` | 4 |
| 30 | `vinu-complete-manager/web/src/components/LlmTracesTab.jsx` | 4 |
| 31 | `vinu-complete-manager/web/src/components/EnrichmentTab.jsx` | 4 |
| 32 | `vinu-complete-manager/web/src/components/ApiCallsTab.jsx` | 4 |
| 33 | `vinu-complete-manager/web/src/components/CorrelationTab.jsx` | 4 |
| 34 | `vinu-complete-manager/web/src/components/StrategyTab.jsx` | 4 |
| 35 | `vinu-complete-manager/web/src/components/StockTab.jsx` | 4 |
| 36 | `vinu-complete-manager/web/src/components/FeaturesTab.jsx` | 4 |
| 37 | `vinu-complete-manager/web/src/components/SimulatorTab.jsx` | 4 |
| 38 | `docker-compose.yml` (modify) | 1 |
