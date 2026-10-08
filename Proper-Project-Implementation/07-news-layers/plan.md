# Plan: the layered news system (vinu-news)

Written 2026-10-08 from the data audit (`06-data-audit/news.md`, findings DA-N1..N11, chain C1) and the design agreed with the user.

## Aim
vinu-news **collects, de-duplicates, links and tags** news from many sources and stores it. It gives **no verdict**. Analysis (price reaction, shock, causality) lives in vinu-initial-analysis as a function of the data available up to a time `t`, so a past range and "now" use the same code. The agent reads the same stored data.

Two rules that every layer follows:
1. **Raw is immutable, derived layers can be rebuilt.** A better similarity rule or entity list can be re-applied to the existing articles without fetching again.
2. **Idempotent and restart-safe.** Running a layer twice on the same input gives the same table. Live and backfill take the same path.

"Known at" time = `first_seen_at` (when we first saw the item), never a later edit time. Replays use it as the as-of cut, so nothing from the future leaks in.

## The five layers

| # | Layer | What it does | Tables / columns | Status |
|---|---|---|---|---|
| 1 | Sources | Many sources behind one interface. Each can be switched off by the operator. Every failure is recorded with a kind (blocked, gone, rate-limited, timeout, network, server, other). After N errors in a row a source is switched off automatically and retried later (1 h, 6 h, 24 h). State changes are logged; `GET /news/sources` reads them out. A new source is one config entry plus one small adapter. | `feed_health` grows: `kind`, `error_kind`, `error_streak`, `off_count`, `auto_disabled_until`, `operator_off`, `last_articles` | BUILT and live 2026-10-08 (problem-log P66); alert channel waits on O4 |
| 2 | Per-source duplicates | The same item from the same source is one row: `first_seen_at`, `last_seen_at`, `seen_count`. If the text really changes, a new revision row is linked to the old one; the old one stays. | `articles` (or `source_items`) + `content_hash`, `first_seen_at`, `last_seen_at`, `seen_count`, `revision_of` | BUILT and live 2026-10-08 (P67-P68) |
| 3 | Cross-source stories | Reports of the same story from different sources become one story with tags: sources list, first source, each source's first time. A later report only updates `last_seen_at` and the sources list; nothing is re-analysed. Compared only within a ticker and a time window. Raw rows are kept so a bad merge can be undone. | `stories(story_id, first_seen_at, last_seen_at, n_sources, sources_json, first_source)`; `articles.story_id` | BUILT and live 2026-10-08 (P67-P68) |
| 4 | Facts per story (once, on first sight) | primary ticker, other tickers mentioned, entities and key words, event tag (earnings, FDA, M&A, guidance ...), sentiment score as a number (FinBERT when models are on, else the rule-based score; never a verdict). | `story_facts(story_id, primary_ticker, other_tickers_json, entities_json, keywords_json, event_tag, sentiment_score, sentiment_method)` | BUILT and live 2026-10-08 (P67-P68) |
| 5 | The table consumers read | One row per (ticker, story), marked primary or mentioned, with times and the layer-4 columns. A time-range query is one indexed read, with an `as_of` cut on `first_seen_at`. | `ticker_news(ticker, story_id, role, first_seen_at, last_seen_at, ...)` | BUILT and live 2026-10-08 (P67-P68) |

Also moves out of vinu-news in this work: the **price reaction** join (it needs stock-price data). It becomes `price_reaction(article, at_time)` in the analysis layer (chain C1 of the audit). The news read no longer calls stock-price.

## Layer 1 in detail (first to build)
- **Two kinds of source**, one health table: RSS feeds (22) and ticker-news providers (Alpaca, FMP, Yahoo).
- **Settings:** `VINU_NEWS_SOURCE_AUTO_OFF_AFTER` (default 10 errors in a row), backoff steps 1 h, 6 h, 24 h. An empty feed with no error is not an error (quiet feeds are normal).
- **Operator switch** is kept in the database (`operator_off`), not in the packaged yaml (the container's code directory is read-only, so the yaml toggles cannot persist).
- **Read-out:** `GET /news/sources` lists every source with its state (`ok`, `failing`, `off: operator`, `off: automatic until <time>`, `off: config`), last error and kind, and an `attention` list in plain words. A WARNING line is logged when a source is switched off automatically and an INFO line when it recovers.
- **Adding a new source:** (1) a config entry (id, kind, url or key name, tier, enabled); (2) for an API, an adapter with `is_configured()` and `fetch_ticker_news()`; (3) nothing else: health, switches, read-out and dedup apply automatically. A test per adapter feeds it a recorded sample.

## Checks for each layer
A guard test on the old behaviour that fails, the fix, a rebuild and recreate of `news-api`, a read of the live logs and tables, and a line in the problem log.

## Out of scope for now
FinBERT on this path needs the models container, which stays dormant; the score column stays empty until it is switched on. An alert channel for source failures waits on the open alert-channel item (O4); until then the read-out is the route and the log.


## Update 2026-10-08: per-ticker databases, one source, analysis snapshots (user decisions)

- **Alpaca only.** The 22 RSS feeds are off (operator switch, kept in the database), FMP and Yahoo are off in the configuration. This keeps live and past news on one pipeline, so the analysis is consistent. Other sources come back later by switching them on; the layers already handle several sources.
- **One database per ticker** (`data/news/tickers/<SYMBOL>.db`), like the price folders. Every layer lives inside each file. A story about two tickers is written to both files with the same article id (accepted duplication). The central database `news_central.db` holds only settings, the watchlist, backfill state and source health. `GET /news/tickers` shows each ticker's dataset and backfill state; `DELETE /news/tickers/{symbol}` drops one.
- **Fresh start.** The old shared file `vinu_news.db` is kept untouched as the archive; the new central database was seeded from it (settings, watchlist, source switches; every backfill reset to pending). Each ticker is refilled from 2023-01-01 through the layers.
- **Analysis reads a frozen copy.** initial-analysis keeps `news_inputs/<SYMBOL>/<from>_<to>.parquet` with a manifest and reads that, not the live store (see problem-log P72). Same rows and columns as before, so no angle changed.
- **Still to do:** the onboarding gate (a ticker is usable only when its prices and news are filled and analysed), the point-in-time universe, a parity check that a snapshot equals what the live store returned as of that time, and switching initial-analysis to the `ticker-news` table.
