# Vinu Features — Textbook (Volume 3)

**Sister volumes:** [vinu-news Textbook (Volume 1)](../../vinu-news/docs/INDEX.md) · [vinu-stock-price Textbook (Volume 2)](../../vinu-stock-price/docs/INDEX.md)

**Yet to build (quick view):** [**Appendix E — Yet to build**](part-5-appendices/apx-e-yet-to-build.md) · [**Appendix F — Issues index**](part-5-appendices/apx-f-issues-index.md) · [News yet to build](../../vinu-news/docs/book/part-5-appendices/apx-e-yet-to-build.md)

Start here for chapter-based documentation. Legacy monolithic guide remains with redirect banner.

## Reading paths

| Path | Chapters | Est. time |
|------|----------|-----------|
| **Operator** | [ch01](part-0-getting-started/ch01-install-first-run.md) → [ch10](part-4-operations/ch10-http-api.md) → [ch11](part-4-operations/ch11-cli-reference.md) → [ch13](part-4-operations/ch13-web-ui.md) | ~30 min |
| **Researcher** | ch01 → [ch03](part-1-presets/ch03-preset-blueprints.md) → [ch04](part-1-presets/ch04-indicator-catalog.md) → [ch08](part-3-data/ch08-sqlite-registry.md) → [ch07](part-2-engine/ch07-manifest-and-parquet.md) | ~45 min |
| **Contributor** | ch02 → [ch05](part-2-engine/ch05-request-lifecycle.md) → ch06 → ch08 → [apx-b](part-5-appendices/apx-b-test-map.md) | ~1.5 hr |

## Chapter catalog

### Part 0 — Getting started

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [**Arch**](ARCHITECTURE.md) | **System architecture** | REVIEW | — | 10 min |
| [00](part-0-getting-started/ch00-preface.md) | Preface & position in Vinu pipeline | REVIEW | — | 5 min |
| [01](part-0-getting-started/ch01-install-first-run.md) | Install, configure, first run | REVIEW | `cli.py` | 15 min |
| [02](part-0-getting-started/ch02-concepts-glossary.md) | Preset, request, run folder, warm-up | REVIEW | — | 10 min |

### Part 1 — Presets

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [03](part-1-presets/ch03-preset-blueprints.md) | Preset blueprints (basic_ta, swing_basic, momentum) | REVIEW | `bigger_recipe/catalog.py` | 10 min |
| [04](part-1-presets/ch04-indicator-catalog.md) | Indicator catalog (23 TA indicators) | REVIEW | `compute/indicators/` | 15 min |
| [05](part-1-presets/ch05-ml-models.md) | ML models (9 sklearn-based models) | REVIEW | `compute/ml_models/` | 10 min |
| [06](part-1-presets/ch06-bigger-recipes.md) | Bigger recipes (8 TA packs + alpha sets) | REVIEW | `compute/bigger_recipe/` | 10 min |
| [07](part-1-presets/ch07-alpha-factors.md) | Alpha factors (101, 158, 360) | REVIEW | `bigger_recipe/_alpha_expr/` | 15 min |
| [08](part-1-presets/ch08-feature-specs.md) | Structured feature specs | REVIEW | `compute/feature_spec.py` | 10 min |

### Part 2 — Engine

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [05](part-2-engine/ch05-request-lifecycle.md) | Request lifecycle (submit → worker → done) | REVIEW | `service.py` | 10 min |
| [06](part-2-engine/ch06-worker-and-oom-safe-load.md) | Worker + OOM-safe parallel processing | REVIEW | `worker/runner.py`, `engine/engine.py` | 15 min |
| [07](part-2-engine/ch07-manifest-and-parquet.md) | Manifest + parquet artifacts | REVIEW | `engine/manifest.py` | 10 min |

### Part 3 — Data

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [08](part-3-data/ch08-sqlite-registry.md) | SQLite registry (thread-safe, WAL, migrations) | REVIEW | `storage/sqlite_backend.py` | 15 min |
| [09](part-3-data/ch09-run-folder-layout.md) | Run folder layout | REVIEW | `engine/engine.py` | 10 min |

### Part 4 — Operations

| Ch | Title | Status | Module | Est. |
|----|-------|--------|--------|------|
| [10](part-4-operations/ch10-http-api.md) | HTTP API reference | REVIEW | `server/` | 10 min |
| [11](part-4-operations/ch11-cli-reference.md) | CLI reference | REVIEW | `cli.py` | 10 min |
| [12](part-4-operations/ch12-config-env.md) | Config & env vars | REVIEW | `config.py` | 10 min |
| [13](part-4-operations/ch13-web-ui.md) | Web UI (React dashboard) | REVIEW | `web/` | 15 min |

### Part 5 — Appendices

| Ch | Title | Status | Est. |
|----|-------|--------|------|
| [A1](part-5-appendices/apx-a-fincept-mapping.md) | Fincept mapping | REVIEW | 5 min |
| [A2](part-5-appendices/apx-b-test-map.md) | Test map | REVIEW | 5 min |
| [A3](part-5-appendices/apx-c-out-of-scope.md) | **Out of scope for v1** | NEW | 10 min |
| [A4](part-5-appendices/apx-d-roadmap-gaps.md) | **Roadmap & gaps** | NEW | 10 min |
| [A5](part-5-appendices/apx-e-yet-to-build.md) | **Yet to build** (TODO only) | NEW | 5 min |
| [A6](part-5-appendices/apx-f-issues-index.md) | **Issues & changelog index** | NEW | 5 min |

## Enhancement task → chapter map

| Task | Chapter | Notes |
|------|---------|-------|
| TASK-F00 | ch13 | Dashboard health fields — delivered 2026-07-06 |
| TASK-F01 | ch06 | Parallel symbol fetching — delivered 2026-07-03 |
| TASK-F02 | ch07 | Cross-symbol feature stacking |
| TASK-F03 | ch05 | Portfolio-level features |
| TASK-F04 | ch05 | Automated model retraining |
| TASK-F05 | ch10 | WebSocket status updates |
| TASK-F06 | ch04 | Feature drift monitoring |

## Legacy guides

| Guide | Status |
|-------|--------|
| [complete_guide_features.md](../complete_guide_features.md) | Redirect banner → this INDEX |

## Issues & changelog

| Date | Summary | Link |
|------|---------|------|
| 2026-07-06 | Dashboard Phase 1 — health fields + 8 new sections | [issue](issues-plan-summary/20260706-issue.md) · [plan](issues-plan-summary/20260706-plan.md) · [summary](issues-plan-summary/20260706-summary.md) |
| 2026-07-03 | Code audit — 37 issues fixed across 6 phases | [issue](issues-plan-summary/20260703-issue.md) · [plan](issues-plan-summary/20260703-plan.md) · [summary](issues-plan-summary/20260703-summary.md) |
