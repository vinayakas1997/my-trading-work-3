# Understanding 3 — Data Layer Enhancement Tasks (vinu-news + vinu-stock-price)

**Audience:** AI coding agents and human implementers  
**Scope:** Enhance only `vinu-news` and `vinu-stock-price` using patterns from the 4 reference repos.  
**Do not:** Clone full qlib / FinRobot / FinRL-Meta / FinRL-Trading repos into Vinu.

**Prerequisites:**
- [`understanding-1.md`](understanding-1.md) — overall architecture
- [`gaps-understaing2.md`](gaps-understaing2.md) — Phase 2 gaps
- [`vinu-news/docs/news_componete_still_missing.md`](../vinu-news/docs/news_componete_still_missing.md)
- [`vinu-stock-price/docs/complete_guide_stock_price.md`](../vinu-stock-price/docs/complete_guide_stock_price.md)

---

## Agent instructions (read first)

When implementing any task below:

1. **Read** the listed reference files in this workspace before writing code.
2. **Implement** only inside the target package (`vinu-news/` or `vinu-stock-price/`).
3. **Match** existing Vinu patterns: `service.py` facade, YAML config, CLI + FastAPI routes, pytest with mocks.
4. **Do not** add new top-level packages unless the task explicitly says so.
5. **Update docs** after each task (see [Documentation update checklist](#documentation-update-checklist)).
6. **Add tests** for every task — no live API keys in CI; use mocks/fixtures.
7. **Mark task status** in the [Task tracker](#task-tracker) table at the bottom of this file.

---

## What we fetch today (baseline)

### vinu-news
- RSS feeds from `vinu_news/rss/config/feeds.yaml` (Tier 1–4)
- Rule enrichment: sentiment, impact, tickers, threads, FTS
- Storage: SQLite `vinu_news/analysis/data/news.db`

### vinu-stock-price
- 1m OHLCV from Polygon → Alpaca → Yahoo (`providers.yaml`)
- Parquet archive + live; query via DuckDB
- Storage: `data/prices/1m/{SYMBOL}/` + `meta.db`

---

# HIGH priority tasks

See [vinu-news-stock-price-enhancement/enhancement-doc1.md](../vinu-news-stock-price-enhancement/enhancement-doc1.md) for full task tables (TASK-N01 through TASK-X01).

---

# Task tracker

| ID | Priority | Status | Completed | Notes |
|----|----------|--------|-----------|-------|
| TASK-N01 | HIGH | DONE | 2026-07-01 | OpenAI-compatible local LLM |
| TASK-N02 | HIGH | DONE | 2026-07-01 | Yahoo ticker news + FMP stub |
| TASK-N03 | HIGH | DONE | 2026-07-01 | Price reaction on read |
| TASK-S01 | HIGH | DONE | 2026-07-01 | Query-time indicators |
| TASK-S02 | HIGH | DONE | 2026-07-01 | Yahoo adj_factor |
| TASK-S03 | HIGH | DONE | 2026-07-01 | Retry + gap validation |
| TASK-X01 | HIGH | DONE | 2026-07-01 | Shared watchlist JSON |
| TASK-N04 | MEDIUM | TODO | | |
| TASK-N05 | MEDIUM | TODO | | |
| TASK-N06 | MEDIUM | TODO | | |
| TASK-S04 | MEDIUM | TODO | | |
| TASK-S05 | MEDIUM | TODO | | |
| TASK-S06 | MEDIUM | TODO | | |
| TASK-X02 | MEDIUM | TODO | | |

---

# Documentation update checklist

After **every** completed task, update package README, `complete_guide_*.md`, `.env.example`, and this tracker.
