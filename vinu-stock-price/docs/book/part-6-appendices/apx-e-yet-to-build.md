# Appendix E — Yet to Build (vinu-stock-price)

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | — |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | — |

**Quick dashboard:** open this chapter when you need **only what is not built yet**. For done + todo together, see [Appendix D — Roadmap](apx-d-roadmap.md). Full specs: [`enhancement-doc1.md`](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md).

**Sister volume:** [vinu-news — Yet to build](../../../../vinu-news/docs/book/part-5-appendices/apx-e-yet-to-build.md)

---

## Open enhancement tasks (vinu-stock-price)

| ID | Priority | Title | Status | Spec | Document when done |
|----|----------|-------|--------|------|-------------------|
| [TASK-S04](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-s04--us-market-calendar-on-live-ingest) | MEDIUM | US market calendar on live ingest | **PARTIAL** | `live/ingest_cycle.py` — skip outside RTH | [ch15](../part-3-ingest/ch15-market-calendar.md) |
| [TASK-S05](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-s05--benchmark-index-symbols) | MEDIUM | Benchmark index symbols | **TODO** | CLI `watchlist --benchmarks SPY,QQQ` | [ch22](../part-5-operations/ch22-cli-reference.md) |
| [TASK-S06](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-s06--fmp-provider-optional) | MEDIUM | FMP OHLCV provider | **TODO** | `providers/fmp.py` + `providers.yaml` | [ch07](../part-1-providers/ch07-yahoo-fmp-fallback.md) |
| [TASK-S07](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#low-priority-tasks) | LOW | Fundamentals sidecar Parquet | **TODO** | Separate tree from candles | [apx-a](apx-a-out-of-scope.md) |
| [TASK-S08](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#low-priority-tasks) | LOW | WebSocket live transport | **TODO** | Sub-minute bars | [ch14](../part-3-ingest/ch14-live-ingest.md) |
| [TASK-S09](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#low-priority-tasks) | LOW | Year-end archive rollover | **TODO** | `backfill/` scheduled freeze | [ch08](../part-2-storage/ch08-data-layout.md) |

### TASK-S04 partial detail

| Done | Not done |
|------|----------|
| `catalog/gap_validation.py` — NYSE session gap counting after backfill | Live ingest skip when market closed |
| `gap_count` on `symbol_catalog` | `is_market_open` in `ingest_log` |
| | Holiday calendar / `pandas_market_calendars` |

---

## Cross-package (stock involvement)

| ID | Priority | Title | Status | Spec |
|----|----------|-------|--------|------|
| [TASK-X02](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-x02--news--candles-event-window-api) | MEDIUM | News + candles event window API | **TODO** | Candle snippet in unified events endpoint |

Primary route likely in vinu-news; requires stock API on `:8081`.

---

## Out of scope v1

See [Appendix A — Out of Scope](apx-a-out-of-scope.md) for explicit v1 exclusions (fundamentals, websocket until requested, etc.).

---

## Recently completed (moved out of this list)

| ID | Chapter |
|----|---------|
| TASK-S01 | [ch19](../part-4-query/ch19-indicators.md) — indicators on read |
| TASK-S02 | [ch12](../part-2-storage/ch12-adjusted-close.md) — `adj_factor` + adjusted query |
| TASK-S03 | [ch16](../part-3-ingest/ch16-retry-gap-validation.md) — retry + gap validation |
| TASK-X01 | [ch25](../part-5-operations/ch25-watchlist-shared.md) — shared watchlist |

---

## How to use this page

1. Pick a **TASK-S*** row → read spec in `enhancement-doc1.md`.
2. Implement in `vinu-stock-price/` only (unless TASK-X*).
3. Add tests + update the **Document when done** chapter.
4. Remove the row from this appendix (or mark **Done** in [apx-d](apx-d-roadmap.md)).

## Related

- [INDEX.md](../../INDEX.md)
- [Appendix D — Roadmap](apx-d-roadmap.md)
- [vinu-news — Yet to build](../../../../vinu-news/docs/book/part-5-appendices/apx-e-yet-to-build.md)
