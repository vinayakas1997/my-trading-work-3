# Appendix E — Yet to Build (vinu-news)


| Field             | Value      |
| ----------------- | ---------- |
| **Package**       | vinu-news  |
| **Module**        | —          |
| **Status**        | REVIEW     |
| **Verified**      | 2026-07-01 |
| **Prerequisites** | —          |


**Quick dashboard:** open this chapter when you need **only what is not built yet**. For done + todo together, see [Appendix D — Roadmap & Gaps](apx-d-roadmap-gaps.md). Full specs: `[enhancement-doc1.md](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md)`.

**Sister volume:** [vinu-stock-price — Yet to build](../../../../vinu-stock-price/docs/book/part-6-appendices/apx-e-yet-to-build.md)

---

## Open enhancement tasks (vinu-news)


| ID                                                                                                                | Priority | Title                            | Status   | Spec                                             | Document when done                                                                               |
| ----------------------------------------------------------------------------------------------------------------- | -------- | -------------------------------- | -------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| [TASK-N04](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-n04--sec-filing-text-ingest)    | MEDIUM   | SEC filing text ingest           | **TODO** | `providers/sec_filings.py` (new)                 | [ch08](../part-1-ingestion/ch08-ticker-news-providers.md)                                        |
| [TASK-N05](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-n05--llm-market--ticker-digest) | MEDIUM   | LLM market / ticker digest       | **TODO** | `analysis/llm/digest.py`, `POST /news/summarize` | [ch15](../part-2-analysis/ch15-llm-layer.md)                                                     |
| [TASK-N06](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-n06--rss-ingestion-hardening)   | MEDIUM   | RSS ingestion hardening          | **TODO** | ETag, backoff, retry in `rss/fetch/`             | [ch05](../part-1-ingestion/ch05-fetch-parse.md), [ch07](../part-1-ingestion/ch07-feed-health.md) |
| [TASK-N07](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#low-priority-tasks)                  | LOW      | Social sentiment feeds           | **TODO** | Optional Stocktwits/Reddit providers             | [ch08](../part-1-ingestion/ch08-ticker-news-providers.md)                                        |
| [TASK-N08](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#low-priority-tasks)                  | LOW      | Python scrapers (BoJ, calendars) | **TODO** | `rss/scrapers/` (new)                            | [ch03](../part-1-ingestion/ch03-rss-architecture.md)                                             |


---

## Partial / stub (not complete)


| Item             | Status        | Notes                                                                 | Chapter when complete                                     |
| ---------------- | ------------- | --------------------------------------------------------------------- | --------------------------------------------------------- |
| FMP ticker news  | **Stub**      | `FmpTickerNewsProvider` exists; returns `[]` until `stock_news` wired | [ch08](../part-1-ingestion/ch08-ticker-news-providers.md) |
| Postgres storage | **Stub v1.1** | `storage/postgres_backend.py` raises `NotImplementedError`            | [ch24](../part-4-operations/ch24-config-env.md)           |
| Web UI           | **Minimal**   | Static `/ui` only; no full Fincept-style dashboard                    | new ops chapter or README                                 |


---

## Cross-package (news involvement)


| ID                                                                                                                     | Priority | Title                           | Status   | Spec                                      |
| ---------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------- | -------- | ----------------------------------------- |
| [TASK-X02](../../../../vinu-news-stock-price-enhancement/enhancement-doc1.md#task-x02--news--candles-event-window-api) | MEDIUM   | News + candles event window API | **TODO** | `GET /news/ticker/{symbol}/events?hours=` |


Depends on [ch16](../part-2-analysis/ch16-price-reaction.md) (done) + vinu-stock-price API.

---

## Out of scope v1 (not scheduled)


| Area                   | Notes                                                        |
| ---------------------- | ------------------------------------------------------------ |
| Fincept Steps 2–5      | Portfolio optimization, execution, paper trading             |
| Full qlib / FinRL port | Reference repos only — see [apx-a](apx-a-fincept-mapping.md) |


---

## Recently completed (moved out of this list)


| ID       | Chapter                                                                         |
| -------- | ------------------------------------------------------------------------------- |
| TASK-N01 | [ch15](../part-2-analysis/ch15-llm-layer.md) — on-demand LLM analyze            |
| TASK-N02 | [ch08](../part-1-ingestion/ch08-ticker-news-providers.md) — ticker news (Yahoo) |
| TASK-N03 | [ch16](../part-2-analysis/ch16-price-reaction.md) — price reaction              |
| TASK-X01 | [ch25](../part-4-operations/ch25-watchlist-settings.md) — shared watchlist      |


---

## How to use this page

1. Pick a **TASK-N*** row → read spec in `enhancement-doc1.md`.
2. Implement in `vinu-news/` only (unless TASK-X*).
3. Add tests + update the **Document when done** chapter.
4. Remove the row from this appendix (or mark **Done** in [apx-d](apx-d-roadmap-gaps.md)).

## Related

- [INDEX.md](../../INDEX.md)
- [Appendix D — Roadmap & Gaps](apx-d-roadmap-gaps.md)
- [news_componete_still_missing.md](../../news_componete_still_missing.md)
- [vinu-stock-price — Yet to build](../../../../vinu-stock-price/docs/book/part-6-appendices/apx-e-yet-to-build.md)

