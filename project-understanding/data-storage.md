# Data Storage Architecture

## Overview

The vinu-components platform consists of **10 Python microservices**, each with its own storage layer. Persistence backends include **SQLite** (relational metadata), **Apache Parquet** (columnar time-series), **JSON/JSONL** (configuration and logs), and **Markdown** (agent memory). One service (vinu-portfolio) is purely **in-memory/stateless**.

All services share a common parent directory layout under `./data/<service-name>/`, mounted into Docker containers at `/data`.

---

## Storage Backend Per Service

| Service | SQLite DB(s) | Parquet | JSON/MD/Other | Data Root (`./data/`) |
|---|---|---|---|---|
| **vinu-news** | `news.db` (12 tables + FTS5) | — | Shared watchlist JSON, LLM cache files | `./data/news/` |
| **vinu-stock-price** | `meta.db` (5 tables) | 1m OHLCV bars per symbol | Shared watchlist JSON | `./data/stock-price/` |
| **vinu-tools** (features) | `meta.db` (1 table) | Run `features.parquet`, optional `scores.parquet` | Run `manifest.md`, ML `oos_metrics.json` | `./data/features/` |
| **vinu-initial-analysis** | `runs.db` (1 table) | 11 angle results per symbol | — | `./data/initial-analysis/` |
| **vinu-strategy** | `meta.db` (2 tables) | Daily weight snapshots | YAML strategy definitions (input only) | `./data/strategy/` |
| **vinu-simulator** | `simulator_meta.db` (2 tables) | equity, weights, trades per run | meta.json, run_card.json, run_card.md | `./data/simulator/` |
| **vinu-research** | `research_meta.db` (3 tables) + `strategy_store.db` (4 tables) | — | Hypotheses, shadows (JSON), LLM cache | `./data/research/` |
| **vinu-portfolio** | **None** | — | — | `./data/portfolio/` (unused) |
| **vinu-live** | `trade_plan_book.db` (3 tables) | — | HALT sentinel file | `./data/live/` |
| **vinu-agent** | `unified_memory.db` (3 tables + FTS5) + `search.db` (FTS5) | — | Sessions (JSON+JSONL), memory (MD), swarm (JSON) | `./data/agent/` |

---

## Data Flow (Inter-Service Dependency Chain)

```
vinu-news ─────────────────────────────────► vinu-initial-analysis ──┐
                                                                      │
vinu-stock-price ───────► vinu-tools ──► vinu-strategy ──► vinu-simulator ──┐
                             │                          │                    │
                             └──► vinu-initial-analysis ─┘                    │
                                                                              ▼
vinu-research ◄──── (reads from simulator, strategy, features) ─────────┘
    │
    ▼
vinu-portfolio (in-memory /stateless — reads strategies from research)
    │
    ▼
vinu-live (reads portfolio + research trade plans, executes trades)
    │
    ▼
vinu-agent (syncs all services into unified memory store via SyncService)
```

### Detailed Data Flow

| Step | From | To | Data Sent |
|------|------|----|-----------|
| 1 | vinu-stock-price | vinu-tools | 1m OHLCV candles via HTTP |
| 2 | vinu-stock-price | vinu-initial-analysis | 1m OHLCV candles via HTTP |
| 3 | vinu-news | vinu-initial-analysis | Enriched news articles via HTTP |
| 4 | vinu-tools | vinu-strategy | Computed features/indicators via HTTP |
| 5 | vinu-initial-analysis | vinu-strategy | Analysis angle results via HTTP |
| 6 | vinu-strategy | vinu-simulator | Strategy weights/signals via HTTP |
| 7 | vinu-strategy | vinu-portfolio | Active strategy list via HTTP |
| 8 | vinu-simulator | vinu-research | Simulation results via HTTP |
| 9 | vinu-research | vinu-portfolio | Approved strategy artifacts via HTTP |
| 10 | vinu-portfolio | vinu-live | Portfolio allocations via HTTP |
| 11 | vinu-research | vinu-live | Trade plan artifacts via HTTP |
| 12 | All services | vinu-agent | Periodic sync of results into unified memory |

---

## Disk Layout (Host File System)

```
data/
│
├── news/                          ← Mounted at /data in news-api container
│   ├── news.db                    ← SQLite — 12 tables + FTS5 (core data)
│   ├── news.db-wal
│   ├── news.db-shm
│   ├── llm_cache.db*              ← SQLite — LLM response cache
│   ├── llm_cache.db-wal
│   ├── llm_calls.jsonl            ← Append-only LLM request/response log
│   └── tickers.csv                ← Ticker reference seed data
│
├── stock-price/                   ← Mounted at /data in stock-api container
│   ├── meta.db                    ← SQLite — catalog, backfill jobs, settings
│   ├── meta.db-wal
│   ├── meta.db-shm
│   └── prices/
│       └── 1m/
│           ├── AAPL/
│           │   ├── archive/
│           │   │   └── 2024.parquet
│           │   └── live/
│           │       ├── 2026.parquet
│           │       └── 2026_20260728.parquet
│           ├── SPY/
│           └── ...
│
├── features/                      ← Mounted at /data in features-api container
│   ├── meta.db                    ← SQLite — feature request registry
│   ├── meta.db-wal
│   ├── meta.db-shm
│   └── runs/
│       └── <id>_<slug>/
│           ├── features.parquet   ← Computed features (OHLCV + indicators)
│           ├── manifest.md        ← Human-readable run summary
│           ├── scores.parquet     ← Optional ML scores
│           └── oos_metrics.json   ← Optional ML out-of-sample metrics
│
├── initial-analysis/              ← Mounted at /data in initial-analysis-api container
│   ├── runs.db                    ← SQLite — run log metadata
│   ├── runs.db-wal
│   ├── runs.db-shm
│   └── analysis/
│       ├── AAPL/
│       │   ├── news_price_causality/
│       │   │   └── <run_id>.parquet
│       │   ├── trend_lifecycle/
│       │   │   └── <run_id>.parquet
│       │   └── ... (11 angles)
│       ├── MSFT/
│       └── ...
│
├── strategy/                      ← Mounted at /data in strategy-api container
│   ├── meta.db                    ← SQLite — strategy registry + run log
│   ├── meta.db-wal
│   ├── meta.db-shm
│   └── weights/
│       └── <strategy_name>/
│           └── 2026/
│               ├── 07/
│               │   └── 29.parquet
│               └── 08/
│                   └── 01.parquet
│
├── simulator/                     ← Mounted at /data in simulator-api container
│   ├── simulator_meta.db          ← SQLite — simulation run metadata + catalog
│   ├── simulator_meta.db-wal
│   ├── simulator_meta.db-shm
│   └── simulations/
│       └── <first_2_hex>/
│           └── <run_id>/
│               ├── equity.parquet    ← Daily equity curve
│               ├── weights.parquet   ← Daily portfolio weights
│               ├── trades.parquet    ← Individual trade records
│               ├── meta.json         ← Run summary
│               ├── run_card.json     ← Comprehensive manifest
│               └── run_card.md       ← Human-readable manifest
│
├── research/                      ← Mounted at /data in research-api container
│   ├── research_meta.db           ← SQLite — research runs + catalog + checkpoints
│   ├── research_meta.db-wal
│   ├── research_meta.db-shm
│   ├── strategy_store.db          ← SQLite — strategy artifacts + bench history
│   ├── strategy_store.db-wal
│   ├── strategy_store.db-shm
│   ├── llm_cache.db               ← SQLite — LLM response cache
│   └── llm_calls.jsonl            ← Append-only LLM request/response log
│
├── portfolio/                     ← Mounted at /data in portfolio-api container
│   └── (empty — service is stateless, no storage used)
│
├── live/                          ← Mounted at /data in live-api container
│   └── trade_plan_book.db         ← SQLite — open/closed positions + fills
│
├── agent/                         ← Mounted at /data in agent-api container
│   ├── unified_memory.db          ← SQLite — synced knowledge base + FTS
│   ├── unified_memory.db-wal
│   ├── unified_memory.db-shm
│   ├── search.db                  ← SQLite FTS5 — session message search
│   ├── sessions/
│   │   └── <session_id>/
│   │       ├── session.json       ← Session metadata
│   │       ├── messages.jsonl     ← Append-only message history
│   │       └── attempts/
│   │           └── <attempt_id>/
│   │               └── attempt.json
│   ├── memory/
│   │   └── <entry_name>.md        ← Persistent markdown memory files
│   └── swarm/
│       └── <run_id>.json          ← Swarm orchestration runs
│
└── shared/                        ← Mounted at /shared in news-api and stock-api
    ├── watchlist.json             ← Cross-service shared watchlist
    ├── watchlist.json.lock        ← File lock for atomic writes
    └── watchlist.json.tmp         ← Staging file for atomic replacement
```

---

## Service-by-Service Detailed Storage

---

### 1. vinu-news

**DB file:** `<data_root>/news.db` (configured via `VINU_NEWS_DB_PATH`)
**Backend:** SQLite via `vinu_lib.sqlite.SQLiteBackend` (thread-local connections, WAL mode)
**Repository:** `NewsRepository` in `analysis/storage/repository.py`
**Additional stores:** `SettingsStore`, `WatchlistStore`, `BackfillStore` (sub-repositories)
**Volume:** `./data/news/` → `/data` in container

#### Tables (12 tables + FTS5)

##### Core News Tables (from `analysis/storage/schema.sql`)

**1. `articles`** — Enriched news articles (leads)

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `headline` | TEXT | News headline |
| `summary` | TEXT | Article summary |
| `source` | TEXT | Source name (e.g. "Benzinga") |
| `link` | TEXT | URL to article |
| `sort_ts` | INTEGER | Unix epoch timestamp for sorting |
| `region` | TEXT | Geographic region |
| `tier` | INTEGER | Priority tier (1-4) |
| `category` | TEXT | News category |
| `priority` | REAL | Computed priority score |
| `sentiment` | TEXT | Sentiment label (bullish/bearish/neutral) |
| `sentiment_score` | REAL | Numeric sentiment score |
| `impact` | TEXT | Impact level |
| `tickers` | TEXT | JSON array of mentioned tickers |
| `lang` | TEXT | Language code |
| `threat_level` | TEXT | Threat assessment level |
| `threat_cat` | TEXT | Threat category |
| `threat_conf` | REAL | Threat confidence score |
| `source_flag` | TEXT | Source reliability flag |
| `entities_json` | TEXT | JSON of extracted entities |
| `cluster_id` | TEXT | Cluster/thread assignment |
| `is_lead` | INTEGER | Whether this is the lead article in a thread |
| `thread_id` | TEXT | FK to `story_threads` |

**2. `article_ticker_mentions`** — Many-to-many article-to-ticker mapping

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `article_id` | TEXT FK | References `articles.id` |
| `ticker` | TEXT | Ticker symbol |
| `dominance` | REAL | Dominance score (how central the ticker is) |
| `is_primary` | INTEGER | Whether this is the primary ticker |

Unique on `(article_id, ticker)`.

**3. `story_threads`** — Cross-article story narratives

| Column | Type | Description |
|--------|------|-------------|
| `thread_id` | TEXT PK | Thread identifier |
| `first_seen_at` | INTEGER | Earliest article timestamp |
| `last_seen_at` | INTEGER | Latest article timestamp |
| `article_count` | INTEGER | Number of articles in thread |
| `lead_headline` | TEXT | Headline of the lead article |
| `dominant_ticker` | TEXT | Most-mentioned ticker |
| `entities_json` | TEXT | JSON of extracted entities |
| `category` | TEXT | Thread category |
| `last_article_id` | TEXT | FK to most recent article |
| `norm_text` | TEXT | Normalized text for matching |

**4. `thread_daily_snapshots`** — Per-thread daily sentiment rollups

| Column | Type | Description |
|--------|------|-------------|
| `thread_id` | TEXT PK | FK to `story_threads` |
| `date` | TEXT PK | Date (YYYY-MM-DD) |
| `article_count` | INTEGER | Articles published that day |
| `bullish_count` | INTEGER | Count of bullish articles |
| `bearish_count` | INTEGER | Count of bearish articles |
| `neutral_count` | INTEGER | Count of neutral articles |
| `flash_count` | INTEGER | Count of flash/breaking articles |

**5. `ticker_daily_stats`** — Per-ticker daily article statistics

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | TEXT PK | Ticker symbol |
| `date` | TEXT PK | Date (YYYY-MM-DD) |
| `article_count` | INTEGER | Total articles mentioning ticker |
| `bullish_count` | INTEGER | Bullish article count |
| `bearish_count` | INTEGER | Bearish article count |
| `neutral_count` | INTEGER | Neutral article count |
| `top_thread_id` | TEXT | Most active thread for the day |

**6. `feed_health`** — Per-RSS-feed health monitoring

| Column | Type | Description |
|--------|------|-------------|
| `feed_id` | TEXT PK | Feed identifier |
| `last_success_at` | INTEGER | Timestamp of last successful poll |
| `last_failure_at` | INTEGER | Timestamp of last failure |
| `fail_streak` | INTEGER | Consecutive failure count |
| `total_polls` | INTEGER | Total poll attempts |
| `total_failures` | INTEGER | Total failures |
| `avg_latency_ms` | REAL | Average response latency |
| `last_error` | TEXT | Error message from last failure |

**7. `news_analysis`** — Cached LLM analysis results

| Column | Type | Description |
|--------|------|-------------|
| `url` | TEXT PK | Article URL |
| `analysis_json` | TEXT | JSON blob of LLM analysis |
| `created_at` | INTEGER | Creation timestamp |

**8. `article_price_reaction`** — Post-article price impact

| Column | Type | Description |
|--------|------|-------------|
| `article_id` | TEXT PK | FK to `articles.id` |
| `price_change_1h` | REAL | Price change 1 hour after article |
| `price_change_1d` | REAL | Price change 1 day after article |
| `computed_at` | INTEGER | When the reaction was computed |

**9. `ticker_reference`** — Ticker symbol lookup

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | TEXT PK | Ticker symbol |
| `name` | TEXT | Company name |
| `aliases` | TEXT | Alternative names/aliases |

##### Supporting Tables (from separate schema files)

**10. `vinu_settings`** (`settings/schema.sql`) — Key-value runtime settings

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT PK | Setting key |
| `value` | TEXT | Setting value |

Used for: mode, poll interval, LLM config, active tiers, backfill config, poll status tracking.

**11. `watchlist_tickers`** (`watchlist/schema.sql`) — Tracked ticker symbols

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | TEXT PK | Ticker symbol |
| `added_at` | INTEGER | When it was added |
| `pending_fetch` | INTEGER | Whether initial fetch is pending |

**12. `backfill_status`** (`backfill/schema.sql`) — Historical backfill progress

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | TEXT PK | Ticker symbol |
| `enabled` | INTEGER | Whether backfill is enabled |
| `status` | TEXT | Current status |
| `backfilled_up_to_ts` | INTEGER | Latest backfilled timestamp |
| `oldest_ts` | INTEGER | Oldest article timestamp |
| `article_count` | INTEGER | Total articles fetched |
| `error_message` | TEXT | Error details if failed |
| `updated_at` | INTEGER | Last update timestamp |

##### FTS5 Virtual Table

**`articles_fts`** — Full-text search index

| Column | Description |
|--------|-------------|
| `headline` | FTS-indexed headline |
| `summary` | FTS-indexed summary |

Tokenizer: `porter unicode61` (stemming + Unicode support). Kept in sync with `articles` via INSERT/DELETE/UPDATE triggers.

#### What Gets Stored

- Enriched news articles with sentiment, impact, threat assessment, named entities
- Ticker-article association with dominance scoring
- Story thread grouping and daily rollups
- Feed health monitoring metrics
- LLM analysis cache
- Price reaction calculations
- Runtime settings and watchlist management
- Backfill progress tracking

---

### 2. vinu-stock-price

**DB file:** `<data_root>/meta.db` (configured via `VINU_STOCK_META_DB_PATH`)
**Bar storage:** Apache Parquet (Zstd compressed) under `<data_root>/prices/1m/<SYMBOL>/`
**Query engine:** DuckDB (in-memory, reads Parquet files via `read_parquet()`)
**Backend:** `MetaBackend` extending `vinu_lib.sqlite.SQLiteBackend`
**Volume:** `./data/stock-price/` → `/data` in container

#### SQLite Tables (5 tables in `meta.db`)

**1. `symbol_catalog`** — Per-symbol metadata and data quality tracking

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | TEXT PK | Ticker symbol (upper case) |
| `provider` | TEXT | Data provider (e.g. "alpaca") |
| `first_bar_ts` | INTEGER | Timestamp of oldest stored bar |
| `last_bar_ts` | INTEGER | Timestamp of newest stored bar |
| `archive_through` | TEXT | Year string, e.g. "2024" |
| `live_file` | TEXT | Path to live parquet file |
| `backfill_status` | TEXT | pending/partial/complete |
| `updated_at` | INTEGER | Last catalog update |
| `has_adj_data` | INTEGER | Whether adjusted data exists |
| `gap_count` | INTEGER | Number of gaps detected |
| `last_validation_at` | INTEGER | Last validation timestamp |

**2. `backfill_jobs`** — Per-symbol per-year historical backfill queue

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `symbol` | TEXT | Ticker symbol |
| `year` | INTEGER | Calendar year |
| `status` | TEXT | queued/running/done/failed |
| `provider` | TEXT | Data provider used |
| `rows_written` | INTEGER | Number of bars written |
| `error` | TEXT | Error message if failed |
| `updated_at` | INTEGER | Last update timestamp |

Unique on `(symbol, year)`.

**3. `ingest_log`** — Append-only audit log for live ingest cycles

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `symbol` | TEXT | Ticker symbol |
| `run_at` | INTEGER | Ingest cycle timestamp |
| `bars_added` | INTEGER | Number of bars added |
| `from_ts` | INTEGER | Start of ingested range |
| `to_ts` | INTEGER | End of ingested range |
| `ok` | INTEGER | Success flag (1/0) |
| `error` | TEXT | Error message if failed |

**4. `vinu_settings`** — Key-value runtime settings

Same schema as vinu-news `vinu_settings`. Keys: `poll_interval_sec`, `default_provider`, `data_root`.

**5. `watchlist_tickers`** — Local ticker watchlist

Same schema as vinu-news `watchlist_tickers`.

#### Parquet Schema (1-minute OHLCV Bars)

File layout: `<data_root>/prices/1m/<SYMBOL>/archive/<YYYY>.parquet` (historical) and `<data_root>/prices/1m/<SYMBOL>/live/<YYYY>*.parquet` (current year, daily shards).

| Column | Arrow Type | Description |
|--------|-----------|-------------|
| `symbol` | string | Ticker symbol |
| `provider` | string | Data provider |
| `bar_ts` | int64 | UTC epoch second |
| `open` | float64 | Open price |
| `high` | float64 | High price |
| `low` | float64 | Low price |
| `close` | float64 | Close price |
| `volume` | float64 | Volume |
| `vwap` | float64 | VWAP (default 0.0) |
| `trades` | int64 | Trade count (default 0) |
| `adj_factor` | float64 | Adjustment factor (default 1.0) |

Compression: Zstd.

#### What Gets Stored

- 1-minute OHLCV price bars in Parquet (one file per year per symbol, plus daily shards for current year)
- Symbol catalog tracking bar ranges, backfill status, data quality
- Backfill job queue (per-symbol per-year)
- Ingest audit log for every live poll cycle
- Runtime settings and watchlist

---

### 3. vinu-tools (Features)

**DB file:** `<data_root>/meta.db` (configured via `VINU_FEATURES_META_DB_PATH`)
**Artifact storage:** Parquet + JSON + Markdown under `<data_root>/runs/<id>_<slug>/`
**Backend:** `SqliteBackend` (custom, not extending `vinu_lib.sqlite.SQLiteBackend`)
**Volume:** `./data/features/` → `/data` in container

#### SQLite Table (1 table in `meta.db`)

**`feature_requests`** — Registry of all feature computation runs

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `title` | TEXT | Human-readable run name |
| `slug` | TEXT | URL/filesystem-safe version of title |
| `symbols` | TEXT | JSON array of ticker symbols |
| `from_ts` | INTEGER | Start timestamp |
| `to_ts` | INTEGER | End timestamp |
| `interval` | TEXT | Candle interval (1m, 5m, 15m, 1h, 1d) |
| `preset` | TEXT | Optional preset name (e.g. "alpha158") |
| `features` | TEXT | JSON array of feature/indicator names |
| `conditions` | TEXT | Optional filter conditions |
| `status` | TEXT | pending/running/done/failed/deleted |
| `file_path` | TEXT | Path to run directory on disk |
| `error_message` | TEXT | Error details if failed |
| `request_hash` | TEXT | SHA-256 dedup hash |
| `row_count` | INTEGER | Number of data rows produced |
| `ml_model` | TEXT | ML model name if ML scoring requested |
| `ml_label` | TEXT | ML label column name if ML scoring requested |
| `created_at` | TEXT | ISO-8601 creation timestamp |
| `updated_at` | TEXT | ISO-8601 last-updated timestamp |

Indexes on `status`, `title`, `request_hash`.

#### Run Artifacts (per run directory)

Each run creates: `<data_root>/runs/<id>_<slug>/`

**`features.parquet`** — Main output

| Columns | Description |
|---------|-------------|
| `ts` | Timestamp |
| `symbol` | Ticker symbol |
| `open`, `high`, `low`, `close`, `volume` | OHLCV base data |
| `...` | One column per computed feature/indicator |

Written via PyArrow `ParquetWriter`.

**`manifest.md`** — Human-readable audit trail containing run metadata, symbol list, date range, feature list, row count.

**`scores.parquet`** (optional) — Same as `features.parquet` plus `ml_score` and `ml_oos` columns.

**`oos_metrics.json`** (optional) — ML out-of-sample metrics: `ml_model`, `ml_label`, `oos_ic`, `train_count`, `test_count`.

#### What Gets Stored

- Feature computation job registry with dedup hash
- Computed technical indicators as Parquet files
- Optional ML model scores and metrics
- Human-readable run manifests

---

### 4. vinu-initial-analysis

**DB file:** `<data_root>/runs.db`
**Analysis storage:** Parquet under `<data_root>/analysis/<SYMBOL>/<ANGLE>/`
**Backend:** `AngleStorage` (Parquet) + `RunLog` (SQLite, custom, not extending `vinu_lib`)
**Volume:** `./data/initial-analysis/` → `/data` in container

#### SQLite Table (1 table in `runs.db`)

**`runs`** — Run log tracking which analyses have been completed

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `symbol` | TEXT | Ticker symbol |
| `angle_name` | TEXT | Analysis angle name |
| `run_id` | TEXT UNIQUE | Unique run identifier (12 hex chars) |
| `started_at` | TEXT | Run start timestamp |
| `analysis_from` | TEXT | Analysis window start |
| `analysis_until` | TEXT | Analysis window end |
| `stored_at` | TEXT | Timestamp of storage |
| `status` | TEXT | Default: 'completed' |
| `error` | TEXT | Error message if failed |
| `row_count` | INTEGER | Number of data rows produced |

Indexes on `symbol`, `angle_name`.

#### Parquet Storage (11 Analysis Angles)

File layout: `<data_root>/analysis/<SYMBOL>/<ANGLE>/<run_id>.parquet`

Each Parquet file has 8 fixed columns plus variable columns per angle:

**Fixed columns on every write:**

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Ticker symbol |
| `angle_name` | string | Angle directory name |
| `time_format` | string | Bar granularity (e.g. "1D", "1H") |
| `run_id` | string | Unique run identifier |
| `started_at` | timestamp | Run start time |
| `analysis_from` | timestamp | Analysis window start |
| `analysis_until` | timestamp | Analysis window end |
| `stored_at` | timestamp | When the write happened |

**Angle-specific columns:**

| Angle | Variable Data Stored |
|-------|---------------------|
| `news_price_causality` | Granger causality test results, Pearson correlation, lag analysis, per-article impact scores (high_bearish/high_bullish), price change impact metrics |
| `trend_lifecycle` | Peak/trough detections, KNN similarity matches, lifecycle stage classification (bull/bear/high_vol/sideways), trade signals, drawdown/recovery outcomes |
| `drawdown_deep_dive` | Drawdown events (peak → trough), max drop %, recovery times, news attribution (news-driven vs market-beta vs unexplained percentages) |
| `shock_personality` | Shock event count, gap-fill rate, volatility persistence, drift persistence in days |
| `shock_clustering` | Shock date clusters, inter-stock correlation during shock periods |
| `regime_analysis` | 4-regime classification stats (bull/bear/high_vol/sideways), regime transition matrix |
| `backtesting_44_metrics` | 17 financial metrics: Sharpe, Sortino, Calmar ratios, CAGR, max DD, win rate, profit factor, VaR 95/99, CVaR, tail ratio, skewness, kurtosis |
| `news_first_analysis` | Session-aware news sentiment baselines — article count, mean sentiment, z-score deviation per trading session |
| `trend_session_structure` | Per-trading-session aggregation of trend lifecycle snapshots — best/worst session analysis |
| `ml_model_pipeline` | OOS IC scores for 9 ML models (Ridge, Random Forest, XGBoost, LightGBM, CatBoost, ElasticNet, KNN, SVR, Gradient Boosting) |
| `pnl_attribution` | Realized PnL statistics: win rate, avg win/loss with 95% confidence intervals, full closed-position history as JSON |

Retention: maximum 10 runs per angle per symbol (oldest deleted on write).

#### What Gets Stored

- 11 different analysis angle results per ticker per run
- Run log tracking which analyses have been completed
- Schema-agnostic Parquet format — each angle defines its own columns
- In-memory TTL cache for impact, correlation, and drawdown queries

---

### 5. vinu-strategy

**DB file:** `<data_root>/meta.db`
**Weight storage:** Parquet under `<data_root>/weights/<STRATEGY>/<YYYY>/<MM>/<DD>.parquet`
**Backend:** `MetaStorage` (SQLite) + `WeightStorage` (Parquet) — both custom, not extending `vinu_lib`
**Volume:** `./data/strategy/` → `/data` in container

#### SQLite Tables (2 tables in `meta.db`)

**1. `strategy_runs`** — Per-evaluation run log

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `strategy_name` | TEXT | Name of the strategy |
| `run_id` | TEXT UNIQUE | Unique run identifier |
| `symbol` | TEXT | Ticker symbol (nullable) |
| `timestamp` | TEXT | Evaluation timestamp |
| `status` | TEXT | pending/running/done/failed |
| `metadata` | TEXT | JSON metadata blob |
| `created_at` | TEXT | Auto-set creation timestamp |

**2. `strategy_registry`** — Active strategy definitions

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT PK | Strategy name |
| `description` | TEXT | Strategy description |
| `schedule` | TEXT | Evaluation schedule (default 'daily') |
| `enabled` | INTEGER | Whether strategy is active (default 1) |
| `updated_at` | TEXT | Last update timestamp |

#### Parquet Schema (Weight Snapshots)

File layout: `<data_root>/weights/<strategy_name>/<YYYY>/<MM>/<DD>.parquet`

| Column | Type | Description |
|--------|------|-------------|
| `date` | timestamp[ms] | Evaluation date |
| `symbol` | string | Ticker symbol |
| `weight` | float64 | Portfolio weight assigned |
| `signal_value` | float64 | Raw signal value |
| `strategy_name` | string | Strategy name |
| `run_id` | string | Run identifier |
| `metadata` | string | JSON metadata |

#### What Gets Stored

- Strategy registry (synced from YAML files on startup)
- Per-evaluation run logs
- Daily weight/signal snapshots as Parquet files
- Strategy definitions not stored in DB — loaded from YAML on each startup

---

### 6. vinu-simulator

**DB file:** `<data_root>/simulator_meta.db`
**Simulation storage:** Parquet + JSON + Markdown under `<data_root>/simulations/<hex>/<run_id>/`
**Backend:** `MetaStorage` (SQLite) + `ResultStorage` (Parquet/JSON) — both custom
**Volume:** `./data/simulator/` → `/data` in container

#### SQLite Tables (2 tables in `simulator_meta.db`)

**1. `simulation_runs`** — Per-simulation metadata and metrics

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | TEXT PK | UUID |
| `strategy_name` | TEXT | Strategy being simulated |
| `timestamp` | TEXT | ISO-8601 run timestamp |
| `config` | TEXT | JSON-serialized `SimulationConfig` |
| `metrics` | TEXT | JSON of all performance metrics |
| `benchmark_metrics` | TEXT | JSON keyed by benchmark ticker |
| `equity_points` | INTEGER | Count of equity curve points |
| `trade_count` | INTEGER | Number of trades executed |
| `config_hash` | TEXT | SHA-256 of config params (for caching) |
| `validation` | TEXT | JSON of validation results |
| `symbols` | TEXT | JSON list of traded symbols |

**2. `simulation_catalog`** — Per-symbol/strategy summary

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | TEXT PK | Ticker symbol |
| `strategy_name` | TEXT PK | Strategy name |
| `last_run_ts` | TEXT | Last run timestamp |
| `last_validated_ts` | TEXT | Last validation timestamp |
| `run_count` | INTEGER | Total run count |
| `last_validation_verdict` | TEXT | Pass/fail verdict |
| `last_sharpe` | REAL | Sharpe of last run |
| `last_max_dd` | REAL | Max drawdown of last run |

#### Run Artifacts (per run directory)

File layout: `<data_root>/simulations/<run_id[:2]>/<run_id>/`

| File | Schema/Content |
|------|----------------|
| `equity.parquet` | `date` (timestamp ms), `portfolio_value` (float64), `daily_return` (float64) |
| `weights.parquet` | `date` + one float column per ticker |
| `trades.parquet` | `date`, `symbol`, `side`, `shares`, `price`, `cost`, `weight_before`, `weight_after` |
| `meta.json` | `{strategy_name, run_id, timestamp}` |
| `run_card.json` | Comprehensive manifest: config, metrics, benchmark_metrics, validation, attribution, artifact checksums |
| `run_card.md` | Human-readable Markdown rendering |

#### What Gets Stored

- Full simulation metadata and metrics in SQLite
- Daily equity curves, weights, and trade records as Parquet
- Benchmark comparisons (SPY, QQQ)
- Validation results (Monte Carlo, bootstrap, walk-forward, stress tests)
- Human-readable run cards

---

### 7. vinu-research

**DB files:** `<data_root>/research_meta.db` + `<data_root>/strategy_store.db`
**Additional JSON stores:** `~/.vinu/hypotheses.json`, `~/.vinu/scheduled_research/jobs.json`, `~/.vinu/shadow_accounts/<id>.json`, judgment log (JSONL)
**Backend:** Both SQLite via `vinu_lib.sqlite.SQLiteBackend` (thread-local, WAL, auto-migration)
**Volume:** `./data/research/` → `/data` in container

#### Database A: `research_meta.db` (3 tables)

**1. `research_runs`** — One row per research loop execution

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `user_idea` | TEXT | The strategy idea |
| `symbol` | TEXT | Ticker (upper-cased) |
| `from_date` | TEXT | ISO date range start |
| `to_date` | TEXT | ISO date range end |
| `status` | TEXT | pending/running/done/failed/deleted/approved |
| `total_iterations` | INTEGER | Number of iterations in loop |
| `best_iteration` | INTEGER | Index of best iteration |
| `best_sharpe` | REAL | Sharpe of best iteration |
| `best_max_dd` | REAL | Max drawdown of best iteration |
| `report_md` | TEXT | Full Markdown report |
| `error_message` | TEXT | Error details if failed |
| `approved` | INTEGER | Boolean approval flag |
| `approved_at` | TEXT | Approval timestamp |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |
| `strategy_code` | TEXT | Generated strategy Python code |
| `deflated_sharpe` | REAL | Deflated Sharpe ratio |
| `holdout_passed` | INTEGER | Nullable boolean |
| `stress_test_passed` | INTEGER | Nullable boolean |

Indexes on `status`, `symbol`.

**2. `research_catalog`** — Per-symbol lifetime research history

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | TEXT PK | Ticker symbol |
| `lifetime_trial_count` | INTEGER | Cumulative iterations |
| `last_run_id` | INTEGER | FK to `research_runs.id` |
| `last_run_ts` | TEXT | Last run timestamp |
| `last_validated_ts` | TEXT | Last validation timestamp |
| `best_sharpe_ever` | REAL | Best Sharpe across all runs |
| `status` | TEXT | active/inactive |
| `total_validated_count` | INTEGER | Total validations performed |
| `last_validation_verdict` | INTEGER | Nullable boolean pass/fail |
| `consecutive_validation_failures` | INTEGER | Consecutive failure count |
| `exhausted` | INTEGER | Flagged at 5+ consecutive failures |

**3. `iteration_checkpoints`** — Per-iteration snapshots for resumability

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | INTEGER PK | FK to `research_runs` |
| `iteration` | INTEGER PK | Iteration number |
| `code` | TEXT | Strategy code at this iteration |
| `metrics` | TEXT | JSON metrics blob |
| `critic_verdict` | TEXT | LLM critic verdict |
| `created_at` | TEXT | Timestamp |

#### Database B: `strategy_store.db` (4 tables)

**1. `artifacts`** — Strategy and trade-plan artifact lifecycle

| Column | Type | Description |
|--------|------|-------------|
| `artifact_id` | TEXT PK | Generated hash `art_{sha256[:12]}` |
| `type` | TEXT | "strategy" or "trade_plan" |
| `name` | TEXT | Artifact name |
| `universe` | TEXT | JSON array of symbols |
| `status` | TEXT | CREATED/BENCHING/ACTIVE/MONITORING/DECAYED/DISABLED |
| `decay_horizon` | INTEGER | Days before decay check (default 60) |
| `signal_definition` | TEXT | Signal generation logic |
| `entry_rules` | TEXT | Entry conditions |
| `exit_rules` | TEXT | Exit conditions |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |
| `strategy_code` | TEXT | Python code for the strategy |
| `source_run_id` | INTEGER | FK to research run that produced it |
| `initial_sharpe` | REAL | Sharpe at promotion |
| `initial_max_dd` | REAL | Max DD at promotion |
| `deflated_sharpe` | REAL | Deflated Sharpe at promotion |
| `holdout_passed` | INTEGER | Holdout test result |
| `stress_test_passed` | INTEGER | Stress test result |
| `last_validated_ts` | TEXT | Last revalidation timestamp |
| `revalidation_count` | INTEGER | Number of revalidations |
| `last_revalidation_verdict` | INTEGER | Pass/fail of last revalidation |
| `trade_plan_data` | TEXT | JSON of frozen TradePlan |

Index on `status`.

**2. `bench_history`** — Daily benchmarking scores per artifact

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `artifact_id` | TEXT FK | References `artifacts` |
| `date` | TEXT | Date |
| `ic` | REAL | Information coefficient |
| `ir` | REAL | Information ratio |
| `ic_positive` | INTEGER | Boolean |
| `sharpe` | REAL | Sharpe ratio |

Index on `artifact_id`.

**3. `decay_snapshots`** — Periodic decay evaluation results

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `artifact_id` | TEXT FK | References `artifacts` |
| `evaluation` | TEXT | HEALTHY/WARNING/DECAYED/CRITICAL |
| `ic_ratio` | REAL | IC ratio metric |
| `rolling_ir` | REAL | Rolling information ratio |
| `ic_positive_ratio` | REAL | Ratio of positive IC days |
| `rolling_sharpe` | REAL | Rolling Sharpe |
| `n_entries` | INTEGER | Number of data points |
| `timestamp` | TEXT | Evaluation timestamp |

Index on `artifact_id`.

**4. `calibration_entries`** — Forecast vs actual outcome scoring

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `artifact_id` | TEXT FK | References `artifacts` |
| `forecast_direction` | TEXT | Predicted direction |
| `actual_return_pct` | REAL | Actual return percentage |
| `forecast_magnitude_pct` | REAL | Predicted magnitude |
| `brier_score` | REAL | Brier score (forecast accuracy) |
| `directional_correct` | INTEGER | Boolean |
| `magnitude_error` | REAL | Magnitude prediction error |
| `timestamp` | TEXT | Timestamp |

Index on `artifact_id`.

#### What Gets Stored

- Research loop runs with full iteration checkpoint history
- Strategy artifacts with lifecycle management (creation → decay)
- Daily bench history for decay detection (IC, IR, Sharpe)
- Forecast calibration tracking for trade plans
- LLM critic verdict accuracy logging

---

### 8. vinu-portfolio

**Storage:** None (purely in-memory)

The service is a **stateless computation layer**. It:
- Fetches active strategies from vinu-research
- Computes risk-parity portfolio allocations in memory via numpy/pandas
- Tracks a single `_peak_value` float in a `PortfolioDrawdownMonitor` (lost on restart)
- Returns computed allocations via HTTP response

The declared `VINU_PORTFOLIO_DATA_ROOT` and `/data` volume are **not used** by any application code.

---

### 9. vinu-live

**DB file:** `<data_root>/trade_plan_book.db`
**Backend:** `BookBackend` extending `vinu_lib.sqlite.SQLiteBackend`
**Volume:** `./data/live/` → `/data` in container

#### SQLite Tables (3 tables in `trade_plan_book.db`)

**1. `open_positions`** — Currently open live positions

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | TEXT PK | Position identifier |
| `symbol` | TEXT | Ticker symbol |
| `side` | TEXT | long/short |
| `qty` | REAL | Quantity |
| `avg_entry` | REAL | Average entry price |
| `realized_pnl` | REAL | Realized PnL (from partial closes) |
| `stop_loss` | REAL | Stop loss price |
| `take_profit` | REAL | Take profit price |
| `opened_at` | TEXT | Open timestamp |
| `updated_at` | TEXT | Last update timestamp |
| `artifact_id` | TEXT | FK to research artifact that authored this position |

**2. `closed_positions`** — Historical closed positions

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | TEXT PK | Position identifier |
| `symbol` | TEXT | Ticker symbol |
| `side` | TEXT | long/short |
| `qty` | REAL | Quantity |
| `avg_entry` | REAL | Average entry price |
| `realized_pnl` | REAL | Realized PnL |
| `stop_loss` | REAL | Stop loss price |
| `take_profit` | REAL | Take profit price |
| `opened_at` | TEXT | Open timestamp |
| `closed_at` | TEXT | Close timestamp |
| `close_price` | REAL | Price at close |
| `artifact_id` | TEXT | FK to research artifact |
| `feedback_processed_at` | TEXT | When Phase 7 feedback loop processed this |

**3. `fills`** — Individual execution fill records

| Column | Type | Description |
|--------|------|-------------|
| `fill_id` | TEXT PK | Fill identifier |
| `symbol` | TEXT | Ticker symbol |
| `side` | TEXT | buy/sell |
| `qty` | REAL | Quantity filled |
| `price` | REAL | Fill price |
| `filled_at` | TEXT | Fill timestamp |
| `position_id` | TEXT | FK to position |
| `commission` | REAL | Commission paid |

#### What Gets Stored

- Live position book (open positions, closed positions, fills)
- Artifact links from positions back to research trade plans
- Feedback processing state tracking
- Daily realized PnL for circuit breaker limit checks

---

### 10. vinu-agent

**DB file:** `<data_root>/unified_memory.db` + `<data_root>/search.db`
**Additional stores:** Session files (JSON+JSONL), persistent memory (Markdown), swarm runs (JSON)
**Backend:** `UnifiedMemoryStore` extending `vinu_lib.sqlite.SQLiteBackend` + `FTSSearch` (standalone SQLite) + file-based stores
**Volume:** `./data/agent/` → `/data` in container

#### SQLite: `unified_memory.db` (3 tables + FTS5)

**1. `memory_entries`** — Unified knowledge base synced from all services

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | Entry identifier |
| `source` | TEXT | Source service (research/simulator/stock_price/news/agent) |
| `source_id` | TEXT | ID in the source service |
| `symbol` | TEXT | Ticker symbol (default '') |
| `memory_type` | TEXT | research_run/strategy_artifact/simulation_run/price_summary/news_article/finding |
| `title` | TEXT | Entry title |
| `content` | TEXT | Full content |
| `summary` | TEXT | Brief summary |
| `metadata` | TEXT | JSON blob |
| `score` | REAL | Relevance score |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

Indexes on `source`, `symbol`, `memory_type`, `(source, symbol)`.

**2. `sync_watermarks`** — Incremental sync tracking

| Column | Type | Description |
|--------|------|-------------|
| `source` | TEXT PK | Source service name |
| `last_sync_at` | TEXT | Last sync timestamp |
| `last_id` | TEXT | Last synced record ID |

**3. FTS5 Virtual Table: `memory_fts`** — Full-text search over memory entries

Columns indexed: `title`, `content`, `summary`, `symbol`, `memory_type`. Tokenizer: `porter unicode61`. Content-sync with `memory_entries`.

#### SQLite: `search.db` (FTS5 only)

**`messages_fts`** — Full-text search index for session messages

| Column | Description |
|--------|-------------|
| `session_id` | Session identifier (UNINDEXED) |
| `role` | Message role (user/assistant) (UNINDEXED) |
| `content` | Message content |
| `message_id` | Message identifier (UNINDEXED) |

#### File-Based Stores

**Session Store** (`<data_root>/sessions/<session_id>/`)

| File | Format | Content |
|------|--------|---------|
| `session.json` | JSON | Session metadata: title, status, timestamps, config |
| `messages.jsonl` | JSONL | Append-only message stream: role, content, metadata |
| `attempts/<attempt_id>/attempt.json` | JSON | ReAct trace: prompt, run_dir, summary, error, metrics |

**Persistent Memory** (`<data_root>/memory/<name>.md`)

| Format | Content |
|--------|---------|
| Markdown | Agent's own notes, one file per memory entry |

**Swarm Store** (`<data_root>/swarm/<run_id>.json`)

| Format | Content |
|--------|---------|
| JSON | Multi-agent run: preset, tasks, results, final report |

#### What Gets Stored

- Unified memory store synced from all upstream services (research results, simulations, price summaries, news articles)
- Agent chat sessions with full message history and ReAct traces
- Persistent markdown notes written by the agent
- Multi-agent swarm orchestration runs
- FTS5 indexes for fast search across memory and messages

---

## Shared Utilities in `vinu-lib`

| Module | Purpose | Used By |
|--------|---------|---------|
| `sqlite.py` | `SQLiteBackend` base class — thread-local connections, WAL mode, upsert/insert_or_ignore, auto-schema init + migrations | vinu-news, vinu-research, vinu-live, vinu-agent |
| `db.py` | `migrate_schema()`, `add_columns()`, `table_has_column()`, `ensure_wal()` — standalone migration functions | vinu-strategy, vinu-simulator, vinu-lib internally |
| `parquet.py` | `ParquetStore` — append, read, read_shard, consolidate, compact with dedup | Available for all services (used directly by stock-price patterns) |
| `config.py` | `ServiceConfig` dataclass + `from_env()` helper | vinu-news, vinu-stock-price |

## Key Architectural Observations

1. **vinu-portfolio is entirely stateless** — its `/data` volume is dead code. All state is fetched on-demand from upstream services.

2. **`data/correlation/` is orphaned** — vinu-initial-analysis writes to `data/initial-analysis/analysis/` instead.

3. **Research hypotheses and shadow profiles** (`~/.vinu/`) go to the container's ephemeral home directory — **lost on container restart** unless a separate volume is mounted.

4. **SQLite is the primary metadata store** across all services that persist data. Parquet is used for bulk time-series (price bars, features, weights, simulation results). JSON/MD files serve as auxiliary logs, manifests, and configuration.

5. **WAL mode is universal** — all SQLite databases use Write-Ahead Logging, enabling concurrent reads with single-writer access across threads.

6. **Thread-local connections** — every SQLite backend opens separate connections per thread, avoiding the "SQLite objects created in a thread can only be used in that same thread" error. The fix applied to vinu-stock-price's `ingest_cycle.py` followed this exact pattern.
