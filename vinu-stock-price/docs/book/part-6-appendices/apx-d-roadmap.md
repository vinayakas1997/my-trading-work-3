# Appendix D — Roadmap & Enhancement Tasks

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | — |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 00, Appendix A |

## Learning objectives

- Map TASK-S01–S04 and TASK-X01 to chapters and implementation status.
- Find full specs in the enhancement doc repository.
- Plan v1.1 work without re-reading the entire codebase.

## 1. Problem this module solves

Enhancement work is specified in [`vinu-news-stock-price-enhancement/enhancement-doc1.md`](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md). This appendix tracks **what landed in vinu-stock-price** as of 2026-07-01, which textbook chapter documents it, and what remains **partial** or **TODO**.

## 2. Position in pipeline

```mermaid
flowchart LR
  DOC[enhancement-doc1.md] --> IMPL[vinu_stock code]
  IMPL --> BOOK[Textbook chapter]
  BOOK --> YOU[Reader]
```

| Step | Input | Output |
|------|-------|--------|
| Read TASK row | priority, target file | Chapter link |
| Check status | code + tests | Implemented / partial / TODO |
| Out of scope | apx-a | Not planned in task set |

## 3. File map

| File | Responsibility |
|------|----------------|
| `vinu-news-stock-price-enhancement/enhancement-doc1.md` | Authoritative TASK definitions |
| `docs/INDEX.md` | Chapter catalog + TASK map |
| `docs/book/part-6-appendices/apx-a-out-of-scope.md` | v1 exclusions |
| Code paths in table below | Implementation |

## 4. Data contracts

### TASK status matrix (2026-07-01)

| Task | Priority | Status | Chapter | Target module | Summary |
|------|----------|--------|---------|---------------|---------|
| TASK-S01 | HIGH | **Implemented** | [ch19](../part-4-query/ch19-indicators.md) | `query/indicators.py` | RSI, MACD, SMA, return, volatility on read |
| TASK-S02 | HIGH | **Implemented** | [ch12](../part-2-storage/ch12-adjusted-close.md) | `models.py`, `indicators.py`, Yahoo parse | `adj_factor` + `apply_adjusted_prices` |
| TASK-S03 | HIGH | **Implemented** | [ch16](../part-3-ingest/ch16-retry-gap-validation.md) | `retry.py`, `gap_validation.py` | Yahoo HTTP retry; backfill `gap_count` |
| TASK-S04 | MEDIUM | **Partial** | [ch15](../part-3-ingest/ch15-market-calendar.md) | `gap_validation.py` only | RTH gap logic yes; live session skip **no** |
| TASK-X01 | HIGH | **Implemented** | [ch25](../part-5-operations/ch25-watchlist-shared.md) | `watchlist/shared.py` | Shared JSON watchlist union sync |

### Related TASKs (not in S01–S04 / X01 set)

| Task | Priority | Status | Notes |
|------|----------|--------|-------|
| TASK-S05 | MEDIUM | TODO | Benchmark presets SPY/QQQ |
| TASK-S06 | MEDIUM | TODO | FMP provider — **vinu-news / future** |
| TASK-S07 | LOW | TODO | Fundamentals sidecar |
| TASK-S08 | LOW | TODO | WebSocket sub-minute |
| TASK-S09 | LOW | TODO | Year archive rollover |
| TASK-X02 | HIGH | TODO | News + candles event window API |

## 5. Logic (step by step)

1. **S01** — `parse_indicator_names` + `apply_indicators` wired in `fetch_candles` and `/candles?indicators=`.
2. **S02** — Yahoo sets `adj_factor`; query `adjusted=true` scales OHLC; `has_adj_data` in catalog.
3. **S03** — `http_get_with_retry` for Yahoo; `count_session_gaps` after each backfill year; warnings in `ingest_log`.
4. **S04 partial** — Session helpers exist; `live/ingest_cycle.py` does **not** check market open; no `is_market_open` column; no holiday calendar.
5. **X01** — `VINU_SHARED_WATCHLIST_PATH` + `POST /watchlist/sync`.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| TASK-S04 future | — | — | Would add session config + ingest_log column |
| TASK-S06 future | `FMP_API_KEY` | — | Not read in v1 |

## 7. Worked examples

### Example A — happy path (verify S01 on running server)

```bash
curl "http://127.0.0.1:8081/candles/AAPL?days=60&indicators=sma_20,rsi_14"
```

### Example B — edge case (S04 not done — live runs Sunday)

```bash
vinu-stock-ingest --once
# Still polls providers; see ch15 for expected behavior
```

### Example C — verify S03 gap_count

```bash
sqlite3 data/meta.db "SELECT symbol, gap_count, last_validation_at FROM symbol_catalog"
```

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| GET | `/candles/{symbol}` | `indicators`, `adjusted` | TASK-S01/S02 |
| POST | `/watchlist/sync` | — | TASK-X01 |
| — | `pytest tests/test_indicators.py` | — | S01/S02 tests |
| — | `pytest tests/test_gap_validation.py` | — | S03 tests |

## 9. SQL / queries (if applicable)

```sql
-- TASK-S03 catalog fields
SELECT symbol, gap_count, last_validation_at, has_adj_data
FROM symbol_catalog;

-- TASK-S04 future: is_market_open column not present in v1 schema
```

## 10. Tests

| Test file | TASK | Asserts |
|-----------|------|---------|
| `tests/test_indicators.py` | S01, S02 | Indicators + adjusted prices |
| `tests/test_provider_retry.py` | S03 | HTTP retry |
| `tests/test_gap_validation.py` | S03, S04 partial | Gap counting |
| `tests/test_watchlist_sync.py` | X01 | Shared JSON |

No test yet for full TASK-S04 live skip.

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Expected live calendar skip | S04 partial | Implement per enhancement-doc1 |
| FMP in docs elsewhere | TASK-S06 | Use Yahoo; see [ch07](../part-1-providers/ch07-yahoo-fmp-fallback.md) |
| TASK doc vs code mismatch | Update lag | Trust chapter `Verified` date |

## 12. Fincept / reference repo mapping

| Enhancement | Reference |
|-------------|-----------|
| TASK-S04 | FinRL-Trading `pandas_market_calendars` |
| TASK-S06 | FinRL-Trading FMP fetcher |
| TASK-S01 | Chart indicators in Fincept terminal |
| Cross-package TASK-X01 | Unified research watchlist |

## 13. Related chapters

- [Appendix A — Out of Scope](apx-a-out-of-scope.md)
- [**Appendix E — Yet to build**](apx-e-yet-to-build.md) (TODO-only dashboard)
- [INDEX.md](../../INDEX.md)
- [enhancement-doc1.md](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md)
- [vinu-news roadmap](../../../../vinu-news/docs/book/part-5-appendices/apx-d-roadmap-gaps.md)
