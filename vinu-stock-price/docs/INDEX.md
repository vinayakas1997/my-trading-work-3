# Vinu Stock Price — Textbook (Volume 2)

**Sister volume:** [vinu-news Textbook (Volume 1)](../../vinu-news/docs/INDEX.md)

**Yet to build (quick view):** [**Appendix E — Yet to build**](book/part-6-appendices/apx-e-yet-to-build.md) · [News yet to build](../../vinu-news/docs/book/part-5-appendices/apx-e-yet-to-build.md)

Start here for chapter-based documentation. Legacy monolithic guides remain with redirect banners.

## Reading paths

| Path | Chapters | Est. time |
|------|----------|-----------|
| **Operator** | [ch01](book/part-0-getting-started/ch01-install-first-run.md) → [ch21](book/part-5-operations/ch21-http-api.md) → [ch22](book/part-5-operations/ch22-cli-reference.md) | ~30 min |
| **Researcher** | ch01 → ch08 → ch17 → [ch18](book/part-4-query/ch18-aggregation.md) → ch20 | ~45 min |
| **Contributor** | ch02 → ch03 → ch08–ch11 → ch13–ch14 → [apx-c](book/part-6-appendices/apx-c-test-map.md) | ~2 hr |

## Chapter catalog

### Part 0 — Getting started

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [00](book/part-0-getting-started/ch00-preface.md) | Preface & relation to vinu-news | REVIEW | — | 5 min |
| [01](book/part-0-getting-started/ch01-install-first-run.md) | Install, backfill, first query | REVIEW | `cli.py` | 15 min |
| [02](book/part-0-getting-started/ch02-concepts-glossary.md) | Bar, archive, live, catalog | REVIEW | — | 10 min |

### Part 1 — Providers

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [03](book/part-1-providers/ch03-provider-architecture.md) | Registry + roles | REVIEW | `providers/registry.py` | 10 min |
| [04](book/part-1-providers/ch04-providers-yaml.md) | Full `providers.yaml` table | REVIEW | `providers/config/` | 10 min |
| [05](book/part-1-providers/ch05-polygon-provider.md) | Polygon adapter | REVIEW | `providers/polygon.py` | 15 min |
| [06](book/part-1-providers/ch06-alpaca-provider.md) | Alpaca adapter | REVIEW | `providers/alpaca.py` | 15 min |
| [07](book/part-1-providers/ch07-yahoo-fmp-fallback.md) | Yahoo fallback provider | REVIEW | `providers/yahoo.py` | 10 min |

### Part 2 — Storage

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [08](book/part-2-storage/ch08-data-layout.md) | Parquet tree + meta.db | REVIEW | `storage/paths.py` | 10 min |
| [09](book/part-2-storage/ch09-bar-record-model.md) | `BarRecord` fields + dedup key | REVIEW | `storage/models.py` | 10 min |
| [10](book/part-2-storage/ch10-catalog-schema.md) | `symbol_catalog`, jobs, ingest_log | REVIEW | `catalog/schema.sql` | 15 min |
| [11](book/part-2-storage/ch11-parquet-io.md) | Read/write/dedupe | REVIEW | `storage/parquet.py` | 15 min |
| [12](book/part-2-storage/ch12-adjusted-close.md) | Adj factor / splits | REVIEW | TASK-S02 | 15 min |

### Part 3 — Ingest

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [13](book/part-3-ingest/ch13-backfill-flow.md) | Year jobs orchestrator | REVIEW | `backfill/` | 15 min |
| [14](book/part-3-ingest/ch14-live-ingest.md) | Live cycle, closed bars | REVIEW | `live/ingest_cycle.py` | 15 min |
| [15](book/part-3-ingest/ch15-market-calendar.md) | NYSE hours skip | REVIEW | TASK-S04 | 10 min |
| [16](book/part-3-ingest/ch16-retry-gap-validation.md) | Retry + gap_count | REVIEW | TASK-S03 | 10 min |

### Part 4 — Query

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [17](book/part-4-query/ch17-query-engine.md) | DuckDB over parquet | REVIEW | `query/engine.py` | 15 min |
| [18](book/part-4-query/ch18-aggregation.md) | 1m → 5m/1h/1d | REVIEW | `query/aggregate.py` | 15 min |
| [19](book/part-4-query/ch19-indicators.md) | RSI, MACD, SMA on read | REVIEW | TASK-S01 | 15 min |
| [20](book/part-4-query/ch20-sql-cookbook.md) | DuckDB research recipes | REVIEW | — | 20 min |

### Part 5 — Operations

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [21](book/part-5-operations/ch21-http-api.md) | Routes + `/ui` | REVIEW | `server/` | 15 min |
| [22](book/part-5-operations/ch22-cli-reference.md) | All `vinu-stock-*` commands | REVIEW | `cli.py` | 10 min |
| [23](book/part-5-operations/ch23-docker.md) | Compose volumes | REVIEW | `docker-compose.yml` | 10 min |
| [24](book/part-5-operations/ch24-service-facade.md) | `StockService` | REVIEW | `service.py` | 10 min |
| [25](book/part-5-operations/ch25-watchlist-shared.md) | Shared watchlist with news | REVIEW | `watchlist/shared.py` | 10 min |
| [26](book/part-5-operations/ch26-config-env.md) | `VINU_STOCK_*` vars | REVIEW | `config.py` | 10 min |

### Part 6 — Appendices

| Ch | Title | Status | Est. |
|----|-------|--------|------|
| [A1](book/part-6-appendices/apx-a-out-of-scope.md) | v1 exclusions | REVIEW | 5 min |
| [A2](book/part-6-appendices/apx-b-troubleshooting.md) | Common failures | REVIEW | 10 min |
| [A3](book/part-6-appendices/apx-c-test-map.md) | tests/ → module | REVIEW | 10 min |
| [A4](book/part-6-appendices/apx-d-roadmap.md) | enhancement TASK-S* | REVIEW | 15 min |
| [A5](book/part-6-appendices/apx-e-yet-to-build.md) | **Yet to build** (TODO only) | REVIEW | 5 min |

## Enhancement task → chapter map

| Task | Chapter | Notes |
|------|---------|-------|
| TASK-S01 | ch19 | Technical indicators |
| TASK-S02 | ch12 | Adjusted close |
| TASK-S03 | ch16 | Retry + gap validation |
| TASK-S04 | ch15 | Market calendar |
| TASK-X01 | ch25 | Shared watchlist sync |

## Legacy guides

| Guide | Status |
|-------|--------|
| [complete_guide_stock_price.md](complete_guide_stock_price.md) | Redirect banner → this INDEX |
| [how-to/README.md](../how-to/README.md) | Examples merged into ch01, ch22, ch23 |
