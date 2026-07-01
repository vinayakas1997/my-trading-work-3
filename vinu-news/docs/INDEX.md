# Vinu News — Textbook (Volume 1)

**Sister volume:** [vinu-stock-price Textbook (Volume 2)](../../vinu-stock-price/docs/INDEX.md)

**Architecture (LLM vs rules):** [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) — one-page diagrams & dependencies

**Yet to build (quick view):** [**Appendix E — Yet to build**](book/part-5-appendices/apx-e-yet-to-build.md) · [Stock price yet to build](../../vinu-stock-price/docs/book/part-6-appendices/apx-e-yet-to-build.md)

Start here for chapter-based documentation. Legacy monolithic guides remain with redirect banners.

## Reading paths

| Path | Chapters | Est. time |
|------|----------|-----------|
| **Architecture** | [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) (LLM vs rules) | ~10 min |
| **Operator** | [ch01](book/part-0-getting-started/ch01-install-first-run.md) → [ch22](book/part-4-operations/ch22-http-api.md) → [ch23](book/part-4-operations/ch23-cli-docker.md) | ~30 min |
| **Researcher** | ch01 → ch17 → ch18 → [ch20](book/part-3-data/ch20-sql-cookbook.md) | ~45 min |
| **Contributor** | ch02 → ch03 → ch10 → ch12 → ch13 → ch14 → [apx-c](book/part-5-appendices/apx-c-test-map.md) | ~2 hr |

## Chapter catalog

### Part 0 — Getting started

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [**Arch**](book/ARCHITECTURE.md) | **System architecture (LLM vs rules)** | REVIEW | — | 10 min |
| [00](book/part-0-getting-started/ch00-preface.md) | Preface & how to read | REVIEW | — | 5 min |
| [01](book/part-0-getting-started/ch01-install-first-run.md) | Install, Docker, first ingest | REVIEW | `rss/`, `server/` | 15 min |
| [02](book/part-0-getting-started/ch02-concepts-glossary.md) | Lead, thread, tier, FTS | REVIEW | — | 10 min |

### Part 1 — Ingestion

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [03](book/part-1-ingestion/ch03-rss-architecture.md) | RSS package overview | REVIEW | `rss/` | 10 min |
| [04](book/part-1-ingestion/ch04-feeds-yaml.md) | `feeds.yaml` full table | REVIEW | `rss/config/` | 10 min |
| [05](book/part-1-ingestion/ch05-fetch-parse.md) | HTTP fetch + RSS parse | REVIEW | `rss/fetch/`, `rss/parse/` | 15 min |
| [06](book/part-1-ingestion/ch06-ingestion-orchestration.md) | Poll → pipeline | REVIEW | `rss/orchestration/` | 15 min |
| [07](book/part-1-ingestion/ch07-feed-health.md) | Feed health table | REVIEW | `rss/storage/feed_health.py` | 10 min |
| [08](book/part-1-ingestion/ch08-ticker-news-providers.md) | Ticker news providers | REVIEW | `providers/` | 15 min |
| [09](book/part-1-ingestion/ch09-collection-filter.md) | Ticker vs all mode | REVIEW | `collection/` | 10 min |

### Part 2 — Analysis

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [10](book/part-2-analysis/ch10-pipeline-overview.md) | `process_batch()` flow | REVIEW | `analysis/pipeline.py` | 15 min |
| [11](book/part-2-analysis/ch11-pre-enrichment.md) | Validate + URL dedup | REVIEW | `pre_enrichment/` | 10 min |
| [12](book/part-2-analysis/ch12-enrichment-overview.md) | 9 stages overview | REVIEW | `enrichment/enrich.py` | 15 min |
| [12a](book/part-2-analysis/ch12a-priority-sentiment-impact.md) | Priority, sentiment, impact | REVIEW | `priority.py`, `sentiment.py`, `impact.py` | 15 min |
| [12b](book/part-2-analysis/ch12b-category-tickers-threat.md) | Category, tickers, threat | REVIEW | `category.py`, `ticker_extractor.py` | 15 min |
| [12c](book/part-2-analysis/ch12c-credibility-language.md) | Credibility, language, summary | REVIEW | `source_credibility.py`, `language.py` | 10 min |
| [13](book/part-2-analysis/ch13-post-enrichment.md) | NER, synonyms, dedup, lead | REVIEW | `post_enrichment/` | 20 min |
| [14](book/part-2-analysis/ch14-story-threads-persist.md) | Threading + persist | REVIEW | `storage/persist.py`, `threading/` | 15 min |
| [15](book/part-2-analysis/ch15-llm-layer.md) | LLM analyze, digest, cache | REVIEW | `analysis/llm/` | 15 min |
| [15b](book/part-2-analysis/ch15b-llm-prompts.md) | LLM prompts reference | REVIEW | `analysis/llm/prompts.py` | 5 min |
| [16](book/part-2-analysis/ch16-price-reaction.md) | News ↔ stock price join | REVIEW | `integrations/`, `price_reaction.py` | 15 min |

### Part 3 — Data

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [17](book/part-3-data/ch17-schema-catalog.md) | All tables index + ER | REVIEW | `storage/schema.sql` | 15 min |
| [18](book/part-3-data/ch18-table-articles-threads.md) | `articles`, `story_threads` | REVIEW | `storage/` | 20 min |
| [19](book/part-3-data/ch19-table-analytics-fts.md) | Snapshots, stats, FTS | REVIEW | `storage/schema.sql` | 15 min |
| [20](book/part-3-data/ch20-sql-cookbook.md) | Research SQL recipes | REVIEW | — | 20 min |
| [21](book/part-3-data/ch21-python-repository-api.md) | `NewsRepository` | REVIEW | `storage/repository.py` | 15 min |

### Part 4 — Operations

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [22](book/part-4-operations/ch22-http-api.md) | Full route reference | REVIEW | `server/` | 15 min |
| [23](book/part-4-operations/ch23-cli-docker.md) | CLI + compose | REVIEW | `cli.py`, `docker-compose.yml` | 10 min |
| [24](book/part-4-operations/ch24-config-env.md) | Env vars + `analysis.yaml` | REVIEW | `config.py`, `analysis/config/` | 10 min |
| [25](book/part-4-operations/ch25-watchlist-settings.md) | Watchlist + shared sync | REVIEW | `watchlist/`, `settings/` | 10 min |
| [26](book/part-4-operations/ch26-service-facade.md) | `NewsService` | REVIEW | `service.py` | 10 min |

### Part 5 — Appendices

| Ch | Title | Status | Est. |
|----|-------|--------|------|
| [A1](book/part-5-appendices/apx-a-fincept-mapping.md) | Fincept step → Vinu module | REVIEW | 10 min |
| [A2](book/part-5-appendices/apx-b-troubleshooting.md) | Common failures | REVIEW | 10 min |
| [A3](book/part-5-appendices/apx-c-test-map.md) | Test file → module map | REVIEW | 10 min |
| [A4](book/part-5-appendices/apx-d-roadmap-gaps.md) | still_missing + enhancement tasks | REVIEW | 15 min |
| [A5](book/part-5-appendices/apx-e-yet-to-build.md) | **Yet to build** (TODO only) | REVIEW | 5 min |

## Enhancement task → chapter map

| Task | Chapter | Notes |
|------|---------|-------|
| TASK-N01 | ch15, ch15b | LLM article analysis + prompts |
| TASK-N02 | ch08 | Ticker-specific news |
| TASK-N03 | ch16 | Price reaction tagging |
| TASK-X01 | ch25 | Shared watchlist sync |

## Legacy guides

| Guide | Status |
|-------|--------|
| [complete_guide_news_analysis.md](complete_guide_news_analysis.md) | Redirect banner → this INDEX |
| [news_derived_tables.md](news_derived_tables.md) | Redirect banner → ch17–ch20 |
| [news_componete_still_missing.md](news_componete_still_missing.md) | → apx-d-roadmap-gaps |
