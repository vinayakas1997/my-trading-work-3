I'm in **Ask mode**, so I can't create the file in your repo. Below is a ready-to-paste document you can save as something like:

`vinu_advanced_understanding/understanding-3-data-enhancements.md`

Or switch to **Agent mode** and ask me to create it.

---

```markdown
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

## Task format

Each task includes:
- **ID** — stable reference for PRs/commits
- **Priority** — HIGH | MEDIUM | LOW
- **Target** — package + module path
- **Reference** — files to read (local repo paths)
- **Implement** — concrete deliverables
- **Achieve** — acceptance criteria (definition of done)
- **Docs to update** — which markdown files to edit after merge

---

# HIGH priority tasks

---

## TASK-N01 — LLM article analysis + cache

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-news/vinu_news/analysis/llm/` (new) + `server/routes_*.py` |
| **Reference** | `new_level_of_research/FinRobot/finrobot/agents/workflow.py`, `prompts.py`; `new_level_of_research/FinRL-Trading/src/data/data_fetcher.py` (`_annotate_sentiment`, `_parse_sentiment_response`) |
| **Implement** | 1. `analyze_article(url_or_id)` → structured JSON: `sentiment_score` float [-1,+1], `confidence` 0–100, `risk_flags` list, `summary` string. 2. SQLite table `news_analysis` (url PK, `analysis_json`, `created_at`). 3. `POST /news/analyze` on-demand (not on every ingest). 4. Env: `OPENAI_API_KEY` or configurable provider. 5. Fail-soft: if LLM down, return 503 + message; ingest unaffected. |
| **Achieve** | Cached second analysis layer beyond rule sentiment; same URL never re-billed within TTL; pytest with mocked LLM response; OpenAPI docs on `/docs`. |
| **Docs to update** | `vinu-news/README.md`, `vinu-news/docs/news_componete_still_missing.md` (mark §1 done), `vinu-news/docs/complete_guide_news_analysis.md` |

---

## TASK-N02 — Ticker-specific news provider

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-news/vinu_news/providers/` (new) + wire into `rss/orchestration/` or `service.py` |
| **Reference** | `new_level_of_research/FinRL-Trading/src/data/data_fetcher.py` (`get_news`); optional `FinRobot/finrobot/data_source/finnhub_utils.py` |
| **Implement** | 1. Pluggable `ticker_news.yaml` (like `feeds.yaml`). 2. Provider interface: `fetch_ticker_news(ticker, from_ts, to_ts) → list[raw_article_dict]`. 3. First provider: Yahoo or FMP (env key). 4. Merge into existing `process_batch()` + `persist_leads()`. 5. Trigger on watchlist poll or `POST /ingest/ticker-news`. |
| **Achieve** | Watchlist symbols get dedicated headlines not only from global RSS regex tickers; dedup by URL still works; tests with fixture JSON. |
| **Docs to update** | `vinu-news/README.md`, new section in `vinu-news/docs/complete_guide_news_analysis.md`, `news_componete_still_missing.md` |

---

## TASK-N03 — Price reaction tagging on news

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-news/vinu_news/analysis/enrichment/` or `analysis/post_enrichment/` + optional `vinu_stock` HTTP client |
| **Reference** | `vinu-stock-price/vinu_stock/server/routes_read.py` (`GET /candles/{symbol}`); `new_level_of_research/FinRL-Trading/src/data/data_fetcher.py` (news+price join concept) |
| **Implement** | 1. After persist (or on query), for each article with primary ticker: fetch candles from vinu-stock-price (`VINU_STOCK_API_URL`, default `http://127.0.0.1:8081`). 2. Compute `price_change_1h`, `price_change_1d` % since `sort_ts`. 3. Store on `articles` new columns OR `article_price_reaction` table. 4. Expose in `GET /news/ticker/{symbol}` and thread timeline API. |
| **Achieve** | News rows show market reaction; works when stock API up; skip gracefully when down; pytest mocks HTTP. |
| **Docs to update** | `vinu-news/docs/news_derived_tables.md`, `vinu_advanced_understanding/understanding-1.md` (cross-link note), `vinu-stock-price/README.md` (consumer note) |

---

## TASK-S01 — Technical indicators on candle query

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-stock-price/vinu_stock/query/indicators.py` (new) + `query/engine.py` + `server/routes_read.py` |
| **Reference** | `new_level_of_research/FinRL-Trading/src/data/data_processor.py` (`_add_technical_indicators`, `_calculate_rsi`, `_calculate_macd`) |
| **Implement** | 1. `GET /candles/{symbol}?indicators=rsi_14,sma_20,macd` (comma-separated). 2. Compute on aggregated bars after DuckDB read (not stored on disk v1). 3. Indicators v1: `sma_5,10,20,50`, `rsi_14`, `macd`, `macd_signal`, `daily_return`, `volatility_20d`. 4. CLI: `vinu-stock-query candles AAPL --indicators rsi_14,sma_20`. |
| **Achieve** | Strategy-ready features without separate `vinu-features` package yet; tests on synthetic parquet; API schema updated. |
| **Docs to update** | `vinu-stock-price/docs/complete_guide_stock_price.md`, `vinu-stock-price/how-to/README.md`, `vinu-stock-price/README.md` |

---

## TASK-S02 — Adjusted close / split factor

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-stock-price/vinu_stock/providers/` + `storage/models.py` + `query/engine.py` |
| **Reference** | `new_level_of_research/qlib/scripts/data_collector/yahoo/collector.py` (`calc_adjusted_price`); `new_level_of_research/FinRL-Trading/src/data/data_fetcher.py` (`adj_close`, `ajexdi`) |
| **Implement** | 1. Extend `BarRecord` with optional `adj_close` or `adj_factor`. 2. Yahoo provider: fetch adj factor; Polygon/Alpaca: document limitation or use split API if available. 3. Query param `adjusted=true` returns split-adjusted OHLC. 4. Backfill job optional one-time adj factor backfill. |
| **Achieve** | Long backtests on split symbols (e.g. AAPL) are not distorted; catalog notes whether adj data present; tests with known split fixture. |
| **Docs to update** | `vinu-stock-price/docs/complete_guide_stock_price.md` (Core data model), `storage/models.py` docstring reflected in guide |

---

## TASK-S03 — Provider retry + bar gap validation

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | `vinu-stock-price/vinu_stock/providers/base.py`, `backfill/year_job.py`, `catalog/store.py` |
| **Reference** | `new_level_of_research/qlib/scripts/data_collector/yahoo/collector.py` (`retry = 5`); FinRL-Meta data processor normalize pattern (`meta/data_processors/_base.py` when available) |
| **Implement** | 1. Decorator `retry_on_transient(n=3, backoff=1.5)` on provider HTTP calls. 2. After backfill year: detect gaps in 1m bars (market hours only if calendar present). 3. Write `gap_count`, `last_validation_at` to `symbol_catalog`. 4. Log warnings in `ingest_log`. |
| **Achieve** | Transient API failures retry; catalog shows data health; pytest mocks timeout then success. |
| **Docs to update** | `vinu-stock-price/docs/complete_guide_stock_price.md` (Catalog section), Coverage UI description in README |

---

## TASK-X01 — Shared watchlist sync

| Field | Value |
|-------|-------|
| **Priority** | HIGH |
| **Target** | Both: `vinu-news/vinu_news/watchlist/` + `vinu-stock-price/vinu_stock/watchlist/` + env bridge |
| **Reference** | `new_level_of_research/FinRL-Trading/src/data/data_store.py` (unified store idea); both existing `watchlist/store.py` |
| **Implement** | 1. Env `VINU_SHARED_WATCHLIST_PATH` → single JSON/SQLite file both packages read (optional mode). 2. `POST /watchlist/sync` on each service pulls from shared file. 3. Docker compose: mount same volume path. 4. Default: keep independent watchlists if env unset (backward compatible). |
| **Achieve** | One ticker add updates both services when sync enabled; tests for read/write; no breaking change when env unset. |
| **Docs to update** | Both READMEs, `vinu_advanced_understanding/gaps-understaing2.md` (note partial `vinu-core`), docker-compose comments in both packages |

---

# MEDIUM priority tasks

---

## TASK-N04 — SEC filing text ingest

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-news/vinu_news/providers/sec_filings.py` (new) |
| **Reference** | `FinRobot/finrobot/data_source/filings_src/sec_filings.py`, `secData.py` |
| **Implement** | Fetch latest 10-K/10-Q/8-K for watchlist tickers; store as articles with `category=FILING`; link to LLM analyze (TASK-N01). |
| **Achieve** | At least 8-K ingest works for one ticker in test fixture; rate-limit SEC requests. |
| **Docs to update** | `vinu-news/docs/news_componete_still_missing.md`, README providers section |

---

## TASK-N05 — LLM market / ticker digest

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-news/vinu_news/analysis/llm/digest.py` + routes |
| **Reference** | `vinu-news/docs/news_componete_still_missing.md` §2–§3; FinRobot agent workflow |
| **Implement** | `POST /news/summarize` (headlines → paragraph); `GET /news/ticker/{symbol}/digest?date=` from `ticker_daily_stats`; 15-min in-memory cache. |
| **Achieve** | Digest cached; uses existing stats table; mocked LLM tests. |
| **Docs to update** | `news_componete_still_missing.md` §2–§3 marked done |

---

## TASK-N06 — RSS ingestion hardening

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-news/vinu_news/rss/fetch/http_client.py`, `feed_health` updates |
| **Reference** | qlib `deco_retry`; `news_componete_still_missing.md` §5 |
| **Implement** | Retry once on timeout; per-feed exponential backoff; optional ETag / If-Modified-Since in feed_health. |
| **Achieve** | Dead feeds backoff; fewer duplicate fetches; tests with mock 304/timeout. |
| **Docs to update** | `vinu-news/docs/complete_guide_news_analysis.md`, `news_componete_still_missing.md` §5 |

---

## TASK-S04 — US market calendar on live ingest

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-stock-price/vinu_stock/live/ingest_cycle.py` |
| **Reference** | `new_level_of_research/FinRL-Trading/src/data/data_fetcher.py` (`pandas_market_calendars`) |
| **Implement** | Skip live append outside NYSE regular session (configurable); flag `is_market_open` in ingest_log. |
| **Achieve** | No bogus overnight minute bars counted as gaps; test with frozen datetime mock. |
| **Docs to update** | `complete_guide_stock_price.md` Live ingest section |

---

## TASK-S05 — Benchmark index symbols

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-stock-price` watchlist presets + docs |
| **Reference** | FinRL-Trading `get_sp500_components`; qlib benchmark configs |
| **Implement** | Document + CLI helper `vinu-stock-query watchlist --benchmarks SPY,QQQ,IWM`; same backfill/live pipeline. |
| **Achieve** | SPY candles queryable alongside AAPL; catalog entry for indices. |
| **Docs to update** | `how-to/README.md`, README |

---

## TASK-S06 — FMP provider (optional)

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-stock-price/vinu_stock/providers/fmp.py` + `providers.yaml` |
| **Reference** | `FinRL-Trading/src/data/data_fetcher.py` FMP paths |
| **Implement** | Add FMP as priority 3 backfill/live when `FMP_API_KEY` set. |
| **Achieve** | Registry fallback chain includes FMP; mock tests. |
| **Docs to update** | README providers table, `providers.yaml` comments |

---

## TASK-X02 — News + candles event window API

| Field | Value |
|-------|-------|
| **Priority** | MEDIUM |
| **Target** | `vinu-news` new route OR thin `vinu-stock-price` proxy |
| **Reference** | qlib point-in-time dataset concept; TASK-N03 output |
| **Implement** | `GET /news/ticker/{symbol}/events?hours=24` → articles + price_change fields + optional candle snippet. |
| **Achieve** | Single API for research notebooks; depends on N03 + stock API. |
| **Docs to update** | `vinu-news/README.md`, `understanding-1.md` correlation note |

---

# LOW priority tasks

| ID | Task | Target | Reference | Achieve |
|----|------|--------|-----------|---------|
| TASK-N07 | Social sentiment feeds | vinu-news providers | FinRobot `reddit_utils.py`, `finnlp_utils.py` | Optional Stocktwits/Reddit; off by default |
| TASK-N08 | Python scrapers (BoJ, calendars) | vinu-news/rss/scrapers/ | `news_componete_still_missing.md` §4 | 1–2 scrapers, fail-soft |
| TASK-S07 | Fundamentals sidecar Parquet | vinu-stock-price | FinRL-Trading `process_fundamental_data` | Separate tree; not in v1 candles |
| TASK-S08 | WebSocket live transport | vinu-stock-price/live/ | FinRL-Meta Alpaca patterns | Sub-minute; explicit out-of-scope until requested |
| TASK-S09 | Year-end archive rollover job | vinu-stock-price/backfill/ | qlib `DumpDataUpdate` | Automated `archive/{YYYY}` freeze |

---

# Documentation update checklist

After **every** completed task, the agent MUST:

| # | Action | Files |
|---|--------|-------|
| 1 | Mark task **DONE** in [Task tracker](#task-tracker) with date | This file |
| 2 | Update package README quick start if CLI/API changed | `vinu-news/README.md` or `vinu-stock-price/README.md` |
| 3 | Update deep guide with new modules, env vars, API tables | `docs/complete_guide_*.md`, `how-to/README.md` |
| 4 | Mark gaps resolved in news status doc | `vinu-news/docs/news_componete_still_missing.md` |
| 5 | Add env vars to `.env.example` | Both packages |
| 6 | Add pytest module; document how to run | Package `tests/` + README |
| 7 | If cross-package: note integration in | `vinu_advanced_understanding/understanding-1.md` or this file |
| 8 | Do **not** create unsolicited new markdown files unless task says so | — |

**Doc style:** Match existing Vinu docs — tables, mermaid optional, code paths as repo-relative links, “Achieve” = testable outcomes.

---

# Suggested implementation order for agents

```
TASK-X01 (shared watchlist)
  → TASK-S01 (indicators)
  → TASK-S02 (adjusted close)
  → TASK-S03 (retry/gaps)
  → TASK-N02 (ticker news)
  → TASK-N01 (LLM analyze)
  → TASK-N03 (price reaction)
  → TASK-X02 (event window)
  → MEDIUM tasks as needed
```

---

# Task tracker

| ID | Priority | Status | Completed | Notes |
|----|----------|--------|-----------|-------|
| TASK-N01 | HIGH | TODO | | |
| TASK-N02 | HIGH | TODO | | |
| TASK-N03 | HIGH | TODO | | |
| TASK-S01 | HIGH | TODO | | |
| TASK-S02 | HIGH | TODO | | |
| TASK-S03 | HIGH | TODO | | |
| TASK-X01 | HIGH | TODO | | |
| TASK-N04 | MEDIUM | TODO | | |
| TASK-N05 | MEDIUM | TODO | | |
| TASK-N06 | MEDIUM | TODO | | |
| TASK-S04 | MEDIUM | TODO | | |
| TASK-S05 | MEDIUM | TODO | | |
| TASK-S06 | MEDIUM | TODO | | |
| TASK-X02 | MEDIUM | TODO | | |
| TASK-N07 | LOW | TODO | | |
| TASK-N08 | LOW | TODO | | |
| TASK-S07 | LOW | TODO | | |
| TASK-S08 | LOW | TODO | | |
| TASK-S09 | LOW | TODO | | |

---

# Agent prompt template (copy per task)

```
Implement {TASK-ID}: {short title}

Read first:
- vinu_advanced_understanding/understanding-3-data-enhancements.md (task spec)
- {reference paths from task table}

Rules:
- Implement only in {target package}
- Add pytest with mocks (no live API keys)
- Update docs per Documentation update checklist
- Mark task DONE in task tracker with today's date

Definition of done:
{paste Achieve column from task}
```
```

---

## How to use this with an AI agent

1. **Save** the file as `vinu_advanced_understanding/understanding-3-data-enhancements.md`.
2. **Link** it from `understanding-1.md` under “Next document”.
3. **Start one task per session**, e.g.:

   > Implement TASK-S01 per `vinu_advanced_understanding/understanding-3-data-enhancements.md`. Update docs when done.

4. Agent should: read references → code → pytest → update README/guides → mark tracker DONE.

