---
name: build-status
status: discussion-phase
purpose: audit of what's actually built in vinu-components today, against 02-api-design.md, 03-storage-design.md, and the 32-method list in 01-present-considerations/ — read-only findings, nothing here is a change yet.
---

# Build Status — Real Implementation vs. the Plan

Read-only audit of `vinu-components/`, scoped to the three in-scope
components: `vinu-news`, `vinu-stock-price`, `vinu-initial-analysis`.

## vinu-news

- **API**: real FastAPI app (`vinu_lib.server.create_app`, prefix `/news/*`,
  no version prefix). Has an ad-hoc fetch/trigger split already
  (`/ingest/trigger`, `/backfill/trigger` + `/backfill/job/{job_id}`,
  `/finbert/backfill` + job polling) — but job state is an **in-memory
  dict, capped at 50, not persisted**, and response shapes are per-endpoint
  Pydantic models, not the planned 5-field envelope.
- **Storage**: real SQLite via `vinu_lib.sqlite.SQLiteBackend`
  (`NewsRepository`) — one of the few real `vinu_lib` reuses. DB is
  `data/news.db` (8MB, live data), path defaults to `Path.cwd()` if
  `VINU_NEWS_DB_PATH` isn't set (cwd-fallback, contradicts the planned
  required-env-var rule). Filename doesn't match the planned
  `vinu_news.db`.
- **Methods**: has its own real NLP pipeline (rule-based NER, a
  VADER-style finance lexicon scorer, genuine FinBERT via
  `transformers.AutoModelForSequenceClassification`, embedding-based
  dedup/clustering, category/priority classifiers, thread matching) —
  loose equivalents of several Section-1 methods
  (NER/sentiment/event-type/triangulation), but **implemented here, not
  in vinu-initial-analysis** where the plan places them.
- **Tests**: 26 files — best-covered of the three.
- **Read**: ~70-80% mature as a standalone pipeline. Gaps vs. plan are
  conformance (URL shape, envelope, root rule, filename), not missing
  functionality.

## vinu-stock-price

- **API**: real FastAPI app (`/stock/*`), `granularity`/`time-range` are
  query params (`interval`, `from`, `to`, `days`), not path segments as
  planned. No `run_id`/envelope.
- **Storage**: Parquet layout close to planned shape —
  `{root}/prices/1m/{SYMBOL}/archive/{year}.parquet` and
  `.../live/{year}.parquet` (planned: `{year}_{YYYYMMDD}.parquet` daily
  shards — not present, live file is year-granularity not day-shard).
  SQLite catalog is `meta.db` (not planned `vinu_stock_price.db`), reuses
  `SQLiteBackend`. Cwd-fallback root, same as news.
  **Zero `.parquet` files exist anywhere in the repo** — no real candle
  data has been fetched yet in this working tree, despite the pipeline
  code + 10 test files looking solid.
- **Read**: core fetch→store→resample→query pipeline is implemented and
  unit-tested, but unconfirmed against real data.

## vinu-initial-analysis — the big gap

- **API**: real FastAPI app (`/analysis/*`). `POST /analysis/run/{ticker}`
  is **fully synchronous** — no `run_id`, no polling, blocks and returns
  inline. `GET /analysis/angle/{angle_name}/{ticker}` is the closest
  thing to planned `fetch`.
- **Storage**: `AngleStorage` writes `{root}/{symbol}/{angle}/{run_id}.parquet`
  — flat two-level, no `{granularity}`/`{tier}` segments, no `_multi/`
  branch. `RunLog` hand-rolls `sqlite3.connect` directly (does **not**
  reuse `SQLiteBackend`, unlike news/stock-price). DB is `runs.db` (not
  planned `vinu_initial_analysis_runs.db`). Pruning-to-last-N-runs is
  confirmed live in `AngleStorage.write()`. **`read_latest()` still
  scans by `mtime`** — confirmed still live — even though `RunLog`
  already has a SQL table with the exact fields needed to fix it; it's
  just not wired in. No real run outputs on disk (one stray HTML file
  only).
- **Methods — the core finding**: 12 real, tested angles exist
  (`backtesting_44_metrics`, `drawdown_deep_dive`, `ml_model_pipeline`,
  `news_first_analysis`, `news_price_causality`, `peer_relative_strength`,
  `pnl_attribution`, `regime_analysis`, `shock_clustering`,
  `shock_personality`, `trend_lifecycle`, `trend_session_structure`) —
  and **none match any of the 32 planned methods by name** (confirmed via
  repo-wide grep: zero hits for kronos/chronos/timesfm/timegpt/moirai/
  moment/timer/lag-llama/patchformer/dlinear/lstm/patchtst/itransformer/
  tft/lpatchtst/tips/arima/kalman/exponential-smoothing/
  cross-attention-gcn/fincast/finmamba/news-embedding-regime-detection,
  and no tfidf-clustering/NER/velocity-spike/triangulation/
  event-tuple-embeddings). GARCH exists but only embedded inside
  `shock_personality` (via `vinu_tools.compute.risk.volatility.garch_volatility`),
  not as a standalone method.
- **Tests**: 17 files; 5 of the 12 real angles
  (`backtesting_44_metrics`, `ml_model_pipeline`, `regime_analysis`,
  `peer_relative_strength`, `news_first_analysis`) have no dedicated test
  file by name.
- **Read**: the runner/storage/API skeleton is real (~60-70% mature for
  what it does), but it's **0% built against the specific 32-method
  list** — this is a scope mismatch, not a completion percentage. All 32
  planned methods would be new builds; GARCH is the one reusable piece of
  logic.

## vinu-lib / vinu-tools — actual reuse today

- `vinu_lib.server.create_app` — used by all 3 (shared FastAPI factory).
- `vinu_lib.sqlite.SQLiteBackend` — used by news + stock-price, **not**
  initial-analysis.
- `vinu_lib.parquet.ParquetStore` — confirmed fully unused, repo-wide.
- `vinu_lib.config` — confirmed fully unused; each component hand-rolls
  its own `config.py` with its own env var names and cwd-fallback.
- `vinu_tools.compute.risk.{covariance,volatility}` — used only by
  `shock_clustering`/`shock_personality` in initial-analysis; not used by
  news or stock-price.

## Gaps vs. the plan — summary

1. **API shape**: none of the 3 components implement the planned
   `/v1/stage1/{component}/{action}/{ticker}/{granularity}/{time-range}[/{method}][/{run-id}]`
   pattern or the 5-field response envelope. Current routes are
   per-component ad hoc REST, no version prefix.
2. **Fetch vs. trigger**: only informally present in vinu-news
   (in-memory, non-persistent job dicts); vinu-initial-analysis's `/run`
   is fully synchronous; vinu-stock-price shows no trigger pattern.
3. **Storage**: cwd-fallback roots live in all 3 (contradicts the
   required-env-var rule); 3 different DB filenames, none matching the
   planned names; the mtime-scan "latest run" bug is confirmed still
   live in vinu-initial-analysis, with the fix's SQL infra already
   sitting unused right next to it.
4. **Biggest gap**: vinu-initial-analysis's 12 real angles have zero
   name-overlap with the 32 planned methods — it's a different,
   already-substantial suite (backtest-metrics/drawdown/trend-lifecycle/
   regime/shock/pnl-attribution), not a partial build of the plan.
   Meanwhile several NLP methods that resemble planned Section-1 methods
   already work, but live in vinu-news instead — a component-boundary
   question (reuse/move vs. rebuild) the plan doesn't yet address.
5. **Real data footprint is thin**: only vinu-news has substantial real
   data on disk; vinu-stock-price has zero parquet files;
   vinu-initial-analysis has no run outputs. Code/tests look reasonably
   mature, but very little of it has been exercised against real data
   yet.

## Related files

- `02-api-design.md` — the API shape none of the 3 components currently
  implement
- `03-storage-design.md` — the storage shape being compared against here
- `01-method-separation.md` / `../01-present-considerations/00-index.md`
  — the 32-method list checked against vinu-initial-analysis's 12 real
  angles
