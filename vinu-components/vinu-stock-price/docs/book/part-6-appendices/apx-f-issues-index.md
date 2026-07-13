# Appendix F — Issues & Changelog Index

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | — |
| **Status** | REVIEW |
| **Verified** | 2026-07-04 |
| **Prerequisites** | None |

## Learning objectives

- View all identified issues, implementation plans, and delivery summaries by date.
- Track the evolution of vinu-stock-price through structured changelog entries.
- Add new issue dates using the provided template.

## 1. Problem this module solves

Issues, plans, and summaries are stored as date-prefixed markdown files in `docs/book/issues-plan-summary/`. This appendix indexes them chronologically so operators and contributors can see what was identified, planned, and delivered on each date.

## 2. Position in pipeline

```mermaid
flowchart LR
  Issues[docs/book/issues-plan-summary/] --> Index[This appendix]
  Index --> Reader[Operator / Contributor]
  Reader --> Book[Textbook chapters]
```

| Step | Input | Output |
|------|-------|--------|
| Identify | Code review / bug report | `*-issue.md` |
| Plan | Issue analysis | `*-plan.md` |
| Deliver | Implementation | `*-summary.md` |
| Index | All three files | This appendix |

## 3. File map

| File | Responsibility |
|------|----------------|
| `docs/book/issues-plan-summary/*-issue.md` | Identified issues per date |
| `docs/book/issues-plan-summary/*-plan.md` | Implementation plan per date |
| `docs/book/issues-plan-summary/*-summary.md` | Delivery summary per date |
| `docs/book/part-6-appendices/apx-f-issues-index.md` | This appendix — date-wise index |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| Date | YYYY-MM-DD | yes | `2026-07-03` |
| Issue file | path | yes | `20260703-issue.md` |
| Plan file | path | yes | `20260703-plan.md` |
| Summary file | path | yes | `20260703-summary.md` |

### Output

| Field | Type | Example |
|-------|------|---------|
| Date group | heading | `## 2026-07-03` |
| File links | table row | `[20260703-issue.md](../issues-plan-summary/20260703-issue.md)` |
| Changes delivered | bullet list | `- Parquet partition pruning via parquet_globs_by_range` |

## 5. Logic (step by step)

1. When new issues are identified, create `YYYYMMDD-issue.md`, `YYYYMMDD-plan.md`, `YYYYMMDD-summary.md` in `docs/book/issues-plan-summary/`.
2. Copy the template block below and append it to this appendix in chronological order.
3. Update `docs/INDEX.md` Part 6 catalog if needed.

---

## Issue entries

### 2026-07-03 — Code Quality & Performance Audit

| Type | File | Description |
|------|------|-------------|
| Issue | [20260703-issue.md](../issues-plan-summary/20260703-issue.md) | 25 identified issues (10 performance, 15 code quality) |
| Plan | [20260703-plan.md](../issues-plan-summary/20260703-plan.md) | 6-phase plan with execution order and testing strategy |
| Summary | [20260703-summary.md](../issues-plan-summary/20260703-summary.md) | 20/25 fixed, 2 already OK, 2 deferred, 21/21 tests passing |

#### Changes delivered

**Phase 1 — Performance (5 items):**
- Parquet partition pruning: DuckDB now uses `parquet_globs_by_range` to scan only relevant year files
- `data_root` SQLite round-trip eliminated: cached in `__init__`, refreshed on `patch_settings`
- `aggregate_bars` redundant double sort removed (trusts DuckDB ORDER BY)
- `_rolling_std` optimized from O(n×period) to O(1) sliding window with running sum/sum_sq
- `_discover_first_year` checks catalog `first_bar_ts` before calling provider API

**Phase 2 — Storage & I/O (2 items):**
- `append_bars` daily-file approach documented; backfill full-rewrite trade-off documented
- Polygon `earliest_available` fallback changed to daily interval (~13k rows vs ~10M)

**Phase 3 — Code Quality & Consistency (4 items):**
- Race condition in `upsert_symbol` fixed via `INSERT ... ON CONFLICT DO UPDATE`
- Schema migration made thread-safe with try/except on `ALTER TABLE ADD COLUMN`
- Double query in `update_bar_range` auto-fixed by UPSERT change
- Live ingest batch-loads all symbols via `list_symbols()` once before loop

**Phase 4 — Provider Retry & Security (3 items):**
- Polygon API key moved from URL query string to `Authorization: Bearer` header
- Standardized HTTP retry: Polygon and Alpaca now use `http_get_with_retry` (previously only Yahoo)
- Defined `TransientProviderError` instead of raising `ConnectionError` for HTTP 429/5xx

**Phase 5 — Server & API (2 items):**
- Backfill runs in background thread; returns job ID immediately; `/backfill/status/{job_id}` endpoint
- Rate limiting via in-process locks prevents concurrent backfill/ingest; returns 409 Conflict

**Phase 6 — Minor Fixes (4 items):**
- Removed dead `_symbol_to_yahoo` function
- `has_adj_data` now checks all providers, not just Yahoo
- Removed dead `interval` column from schema
- Polygon `fetch_bars` now uses interval param to select timespan

---

## Template for future entries

Copy this block when adding a new issue date:

```markdown
### YYYY-MM-DD

| Type | File | Description |
|------|------|-------------|
| Issue | [YYYYMMDD-issue.md](../issues-plan-summary/YYYYMMDD-issue.md) | ... |
| Plan | [YYYYMMDD-plan.md](../issues-plan-summary/YYYYMMDD-plan.md) | ... |
| Summary | [YYYYMMDD-summary.md](../issues-plan-summary/YYYYMMDD-summary.md) | ... |

#### Changes delivered
- ...
```

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| — | — | — | Reference appendix only |

## 7. Worked examples

### Example A — add a new issue date

1. Create `20260801-issue.md`, `20260801-plan.md`, `20260801-summary.md` in `docs/book/issues-plan-summary/`.
2. Copy the template block above and paste it before the template section.
3. Replace `YYYY-MM-DD` with `2026-08-01` and fill in descriptions.

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| — | — | — | Documentation only |

## 9. SQL / queries (if applicable)

None — this index references markdown files, not database tables.

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| — | No automated tests for issue tracking |

## 11. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Missing issue entry | Not yet indexed | Add entry using template |
| Stale description | Issue updated but appendix not | Update the changes list |
| Wrong file link | Path changed | Use relative path from `apx-f-issues-index.md` |

## 12. Fincept / reference repo mapping

| Reference | This appendix |
|-----------|---------------|
| `critical-issues/vinu-stock-price-issues/` | Source audit files mirrored into book |
| `enhancement-doc1.md` | Cross-service task specs referenced in issue plans |

## 13. Related chapters

- [docs/INDEX.md](../../INDEX.md) — master catalog
- [Appendix D — Roadmap](apx-d-roadmap.md)
- [Appendix E — Yet to Build](apx-e-yet-to-build.md)
- [Chapter 00 — Preface](../part-0-getting-started/ch00-preface.md)
