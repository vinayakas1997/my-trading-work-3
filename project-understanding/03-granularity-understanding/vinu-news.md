# vinu-news

## What it is

Ingests financial news (RSS feeds + provider APIs), runs it through a
multi-stage enrichment/dedup/clustering pipeline, and serves it back.
Feeds `news_price_causality` (vinu-initial-analysis) and every
news-aware angle/step downstream.

## Trigger / cadence

**Three independent loops**, deliberately separate processes so none can
delay another (`cli.py`):

1. **RSS ingest** (`ingest_main`): default **600 seconds (10 min)**
   (`DEFAULT_POLL_INTERVAL_SEC = 600`, `VINU_NEWS_POLL_INTERVAL_SEC`).
   Adaptive sleep — wakes on a short tick to re-check whether
   `service.get_settings().poll_interval_sec` (a live-patchable setting)
   changed, rather than sleeping the full interval blindly.
2. **FinBERT scoring** (`finbert_main`): default **60 seconds**, a
   *separate* backfill sweep — explicitly not a step inside the ingest
   loop, "so it never delays (or is delayed by) ingestion" (the code's
   own comment). Sweeps up to 500 unscored articles per pass, keeps
   sweeping with no sleep until caught up, then sleeps the interval.
3. **Provider backfill** (`backfill_main`): default 300s, pulls from
   Alpaca/FMP/Yahoo's own news APIs (`providers/`) — a second, distinct
   news source from the RSS feeds, used to backfill/supplement.

## Pipeline

**RSS ingest cycle** (`rss/orchestration/ingestion_pipeline.py::run_ingestion`,
called every 10 min):
1. `load_feeds()` — reads the configured RSS feed list
   (`rss/config/feed_loader.py`).
2. `poll_all_feeds(feeds)` — fetches every feed in parallel
   (`rss/fetch/parallel_fetcher.py`), each parsed
   (`rss/parse/rss_parser.py`) into raw article dicts. Per-feed health
   (success/fail, article count) recorded (`rss/storage/feed_health.py`).
3. `process_batch(raw_articles)` (`analysis/pipeline.py`) — the real
   enrichment pipeline, 4 stages in order:
   - **Validate** (`pre_enrichment/validate_raw.py`) — drops malformed
     entries.
   - **URL dedup** (`pre_enrichment/url_dedup.py`) — drops exact
     duplicate links before the expensive enrichment work runs on them.
   - **Enrich**, per article (`enrichment/enrich.py::enrich_article`,
     each sub-step individually feature-flagged via `settings.enrichment`):
     summary cleanup → priority classification → sentiment scoring
     (fast, rule-based — `enrichment/sentiment.py`, NOT FinBERT, which
     runs later/async) → impact classification (from priority + sentiment) →
     category refinement → ticker extraction (against the watchlist) →
     language detection → threat classification → source-credibility
     flag → ticker-dominance scoring. Every sub-step degrades gracefully
     to a safe default (`NEUTRAL`/`LOW`/`[]`/etc.) when its flag is off,
     never blocks the record from being created.
   - **Post-process** (`post_enrichment/post_process.py::post_process_batch`):
     NER entity extraction per article → headline cleanup + text
     normalization (synonym map) → **cosine-similarity clustering**
     (`post_enrichment/cosine_dedup/cluster.py` — groups articles that
     are the same underlying story from different sources) → **lead
     selection** (`lead_pick/select_lead.py` — one canonical "lead"
     article per cluster; the rest marked as duplicates of it, not
     discarded, just not the primary record).
4. `persist_leads()` (`analysis/storage/persist.py`) writes the surviving
   lead articles to SQLite/Postgres (`storage/sqlite_backend.py` /
   `postgres_backend.py`, pluggable via `storage/factory.py`), including
   **thread assignment** (`storage/threading/assign.py`/`matcher.py` —
   groups a developing story's articles across time into one persistent
   "thread", not just one cluster per poll cycle) and full-text search
   indexing (`storage/fts.py`).

**FinBERT sweep** (separate loop, every ~60s): `service.backfill_finbert_sentiment(limit=500)`
re-scores articles' sentiment with the heavier FinBERT model
(`enrichment/finbert_sentiment.py`), overwriting the fast rule-based
sentiment computed during ingest — the two-tier design: never block
ingestion on a slow model, upgrade the sentiment score asynchronously
after the fact.

**Provider backfill** (separate loop, every 300s): a second news source
entirely — Alpaca/FMP/Yahoo's own news endpoints
(`providers/registry.py`), stored via `backfill/store.py`, not the RSS
pipeline above.

## Storage

- SQLite (default) or Postgres (`storage/factory.py` picks by config) —
  articles, ticker mentions, threads, feed health.
- Full-text search index (`storage/fts.py`) backing `GET /news/search`.

## Talks to

- **Outbound**: RSS feeds directly, Alpaca/FMP/Yahoo news provider APIs,
  `vinu-stock-price` (`integrations/stock_price.py` — for context like
  price-reaction scoring, `post_enrichment/price_reaction.py`).
- **Inbound**: `vinu-initial-analysis`'s `NewsClient`
  (`news_price_causality` angle, novelty/impact scoring), `vinu-agent`'s
  `/track` command (adds a ticker to this service's watchlist via
  `POST /news/watchlist/tickers`), anything reading
  `GET /news/ticker/{symbol}`, `/news/high-impact`,
  `/news/threads/active` for a human- or LLM-readable news view.
