# Appendix F — Issues & changelog

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |

## 2026-07-06

- Created docs/book structure with 28 chapters across 6 parts + appendices
- Initial release of vinu-correlation documentation

## 2026-07-03

- Initial project scaffold
- Engine modules: impact, correlation, granger, event_study, drawdown, baseline, market_hours
- Storage: Parquet backend with DuckDB queries
- CLI: serve, compute, compact, query
- HTTP API: FastAPI with 6 read routes
- Web UI: React dashboard
- Docker support with host.docker.internal fallback
