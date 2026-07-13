# Vinu Correlation — Textbook (Volume 3)

**Sister volumes:** [vinu-news (Volume 1)](../../vinu-news/docs/INDEX.md) · [vinu-stock-price (Volume 2)](../../vinu-stock-price/docs/INDEX.md)

**Architecture:** [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) — one-page diagrams & dependencies

**Yet to build (quick view):** [**Appendix E — Yet to build**](book/part-6-appendices/apx-e-yet-to-build.md) · [**Appendix F — Issues index**](book/part-6-appendices/apx-f-issues-index.md)

Start here for chapter-based documentation.

## Reading paths

| Path | Chapters | Est. time |
|------|----------|-----------|
| **Architecture** | [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) | ~10 min |
| **Operator** | [ch01](book/part-0-getting-started/ch01-install-first-run.md) → [ch22](book/part-5-operations/ch22-http-api.md) → [ch23](book/part-5-operations/ch23-cli-reference.md) → [ch25](book/part-5-operations/ch25-docker.md) | ~30 min |
| **Researcher** | ch01 → ch07 → ch08 → ch10 → [ch20](book/part-3-storage/ch17-backend-read-write.md) → ch20 | ~45 min |
| **Contributor** | ch02 → ch03 → ch07–ch14 → ch15–ch18 → [apx-c](book/part-6-appendices/apx-c-test-map.md) | ~2 hr |

## Chapter catalog

### Part 0 — Getting started

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [**Arch**](book/ARCHITECTURE.md) | **System architecture** | DRAFT | — | 10 min |
| [00](book/part-0-getting-started/ch00-preface.md) | Preface & how to read | DRAFT | — | 5 min |
| [01](book/part-0-getting-started/ch01-install-first-run.md) | Install, serve, first compute | DRAFT | `cli.py`, `Dockerfile` | 15 min |
| [02](book/part-0-getting-started/ch02-concepts-glossary.md) | Impact, correlation, lag, drawdown, baseline | DRAFT | — | 10 min |

### Part 1 — Data sources

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [03](book/part-1-sources/ch03-source-architecture.md) | Data source architecture | DRAFT | `clients/` | 10 min |
| [04](book/part-1-sources/ch04-news-client.md) | News API client | DRAFT | `clients/news_client.py` | 10 min |
| [05](book/part-1-sources/ch05-price-client.md) | Price API client | DRAFT | `clients/price_client.py` | 10 min |
| [06](book/part-1-sources/ch06-net-layer.md) | HTTP net layer & Docker fallback | DRAFT | `net.py` | 10 min |

### Part 2 — Engine

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [07](book/part-2-engine/ch07-impact-analysis.md) | News impact analysis | DRAFT | `engine/impact.py` | 15 min |
| [08](book/part-2-engine/ch08-correlation-metrics.md) | Pearson correlation & bootstrap CI | DRAFT | `engine/correlation.py` | 15 min |
| [09](book/part-2-engine/ch09-lag-analysis.md) | News–price lag analysis | DRAFT | `engine/correlation.py` | 10 min |
| [10](book/part-2-engine/ch10-granger-causality.md) | Granger causality test | DRAFT | `engine/granger.py` | 15 min |
| [11](book/part-2-engine/ch11-event-study.md) | Event study & abnormal returns | DRAFT | `engine/event_study.py` | 15 min |
| [12](book/part-2-engine/ch12-drawdown-attribution.md) | Drawdown detection & attribution | DRAFT | `engine/drawdown.py` | 15 min |
| [13](book/part-2-engine/ch13-baseline-deviation.md) | Baseline & news volume deviation | DRAFT | `engine/baseline.py` | 10 min |
| [14](book/part-2-engine/ch14-market-hours.md) | Market hours & session awareness | DRAFT | `engine/market_hours.py` | 10 min |

### Part 3 — Storage

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [15](book/part-3-storage/ch15-parquet-layout.md) | Parquet directory layout | DRAFT | `storage/paths.py` | 10 min |
| [16](book/part-3-storage/ch16-schemas-models.md) | Arrow schemas & models | DRAFT | `storage/models.py` | 10 min |
| [17](book/part-3-storage/ch17-backend-read-write.md) | Read/write via DuckDB + Parquet | DRAFT | `storage/backend.py` | 15 min |
| [18](book/part-3-storage/ch18-compaction.md) | Parquet compaction | DRAFT | `storage/backend.py` | 10 min |

### Part 4 — Compute

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [19](book/part-4-compute/ch19-compute-pipeline.md) | Compute pipeline | DRAFT | `api.py` `compute_and_store` | 15 min |
| [20](book/part-4-compute/ch20-incremental-mode.md) | Incremental vs full recompute | DRAFT | `storage/backend.py` | 10 min |
| [21](book/part-4-compute/ch21-continuous-loop.md) | Continuous polling loop | DRAFT | `cli.py` `--continuous` | 10 min |

### Part 5 — Operations

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [22](book/part-5-operations/ch22-http-api.md) | HTTP API route reference | DRAFT | `server/` | 15 min |
| [23](book/part-5-operations/ch23-cli-reference.md) | CLI command reference | DRAFT | `cli.py` | 10 min |
| [24](book/part-5-operations/ch24-web-ui.md) | Web UI dashboard | DRAFT | `web/` | 10 min |
| [25](book/part-5-operations/ch25-docker.md) | Docker & compose | DRAFT | `Dockerfile` | 10 min |
| [26](book/part-5-operations/ch26-config-env.md) | Config & env vars | DRAFT | `config.py`, `.env.example` | 10 min |
| [27](book/part-5-operations/ch27-cache-layer.md) | In-memory cache layer | DRAFT | `cache.py` | 10 min |
| [28](book/part-5-operations/ch28-service-facade.md) | Service facade | DRAFT | `service.py`, `api.py` | 10 min |

### Part 6 — Appendices

| Ch | Title | Status | Est. |
|----|-------|--------|------|
| [A1](book/part-6-appendices/apx-a-fincept-mapping.md) | Fincept step → Vinu module | DRAFT | 10 min |
| [A2](book/part-6-appendices/apx-b-troubleshooting.md) | Common failures | DRAFT | 10 min |
| [A3](book/part-6-appendices/apx-c-test-map.md) | Test file → module map | DRAFT | 10 min |
| [A4](book/part-6-appendices/apx-d-roadmap-gaps.md) | Gaps & enhancement tasks | DRAFT | 15 min |
| [A5](book/part-6-appendices/apx-e-yet-to-build.md) | **Yet to build** (TODO only) | DRAFT | 5 min |
| [A6](book/part-6-appendices/apx-f-issues-index.md) | **Issues & changelog** (date-wise index) | DRAFT | 5 min |

## Enhancement task → chapter map

| Task | Chapter | Notes |
|------|---------|-------|
| TASK-C01 | ch08, ch09, ch10 | Advanced correlation metrics |
| TASK-C02 | ch07, ch12 | Impact + drawdown integration |
| TASK-C03 | ch19–ch21 | Batch/multi-symbol compute |
| TASK-C04 | ch24 | Web UI charts & filtering |
