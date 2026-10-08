# Data audit: vinu-news

Checked 2026-10-08 on the running stack (`news-api`, database `vinu_news.db`). Counts are from that day.

## What triggers it

- **Poll cycle** (every 600 s; setting `poll_interval_sec`): reads the RSS feeds and the news providers (Alpaca/Benzinga, FMP, Yahoo), keeps lead articles, enriches, stores. Last poll: 770 raw, 673 leads, 16 kept after the filter, 0 new.
- **Backfill** (once per watchlist ticker): 50 tickers, all `completed`, 44,334 articles.
- **On demand** (price reaction): computed when someone asks for a ticker's news, then stored.

## Data items

### N1 Article  `articles` (55,156 rows, oldest 2012, newest today)
- **Producer:** enrichment pipeline (`analysis/enrichment/enrich.py`) after each poll or backfill.
- **Format:** one row per article: `id, headline, summary, source, link, sort_ts, published_at, ingested_at, region, tier, category, priority, sentiment (BULLISH|BEARISH|NEUTRAL), sentiment_score (int, bullish about +2.7 on average, bearish -2.1), impact (LOW|MEDIUM|HIGH), threat_level, threat_cat, threat_conf, tickers (JSON list), entities_json, cluster_id, is_lead, thread_id, finbert_score, finbert_label, lang, source_flag`.
  Example: `BENZINGA, "Why is AbbVie (ABBV) Stock Trending After Hours?", BULLISH, 4, impact MEDIUM, tickers ["ABBV","FDA"]`.
- **Access:** `GET /news/ticker/{symbol}` (with price reaction, `as_of` clamp), `/news/search`, `/news/latest`, `/news/high-impact`, `/news/watchlist/news`, `/news/articles/since`.
- **Consumers (found in code):**
  - initial-analysis `NewsClient.get_ticker_news` -> `runner._fetch_news` -> angles `shock_personality` (time only: has news near a shock), `drawdown_deep_dive` (news inside a drawdown), `news_price_causality` (headline, sentiment, sentiment_score, novelty, session; feeds a significance model), `signal_evidence`. This is the one consumer that uses the data well.
  - agent `get_news` tool (whole JSON). The tool is found by auto-discovery; no agent definition names it (see DA-N9).
  - agent `trade_plan_tool._fetch_news` -> "News Context" table in a trade plan (5 rows: date, headline, sentiment, source), via `/news/search`.
  - agent memory `sync_news` -> memory entries per article, via `/news/search`.
- **Why:** the only market-moving text the system has.
- **Verdict:** used well by initial-analysis; agent plan and memory readers were `wrong shape` (fixed, DA-N1).
- **Fill rates:** `finbert_score` 0 of 55,156 (see DA-N5); `entities_json` has people or countries on 15,870 (29%).

### N2 Ticker mention  `article_ticker_mentions` (100,339 rows)
- **Producer:** `analysis/enrichment/article_splitter.py` (one row per ticker in an article, with a dominance score and a primary flag).
- **Format:** `article_id, ticker, dominance (0-1), is_primary`. Tickers per article: 1 (26,752), 2 (16,964), 3 (7,706), 4+ (4,000).
- **Access:** inside `GET /news/ticker/{symbol}` (columns `dominance`, `is_primary`, `mention_ticker` ride along).
- **Consumers:** the ticker query itself (finds an article by ticker). The dominance number is returned but no reader was found using it; `news_price_causality` recomputes "primary" and "ticker count" from the tickers list. The price-reaction code takes `tickers[0]`, not the dominant ticker (DA-N10).
- **Verdict:** `single use` (lookup only).

### N3 Story thread  `story_threads` (55,155) and N4 `thread_daily_snapshots` (57,336)
- **Producer:** `analysis/storage/threading/` (groups articles of one story).
- **Format:** thread: first/last seen, article count, lead headline, dominant ticker, entities. Snapshot: per day counts of bullish/bearish/neutral/flash.
- **Access:** `/news/threads/active`, `/news/threads/{id}`, `/news/threads/{id}/timeline`.
- **Consumers:** none found outside vinu-news (no caller of these routes in any service).
- **Properties:** 54,946 of 55,155 threads hold exactly one article. Threading groups almost nothing.
- **Verdict:** `no reader`, and `computes no grouping` (DA-N4).

### N5 Ticker daily stats  `ticker_daily_stats` (34,308)
- **Producer:** `analysis/storage/persist.py` on every insert.
- **Format:** `ticker, date, article_count, bullish_count, bearish_count, neutral_count, top_thread_id`. Example: `AMZN 2026-10-08: 17 articles, 11 bullish, 6 neutral`.
- **Access:** `GET /news/stats/ticker/{symbol}`.
- **Consumers:** none found. This is the compact daily "news mood per ticker" that a strategy, the screener or the portfolio could read; nobody does.
- **Verdict:** `no reader` (DA-N8, the most useful unused item).

### N6 Price reaction  `article_price_reaction` (17,051)
- **Producer:** `analysis/post_enrichment/price_reaction.py`, a read-through cache: when a ticker's news is requested, the stock-price candles around each article are fetched and the 1-hour and 1-day change saved.
- **Format:** `article_id, price_change_1h, price_change_1d, computed_at`. 1h on all 17,051, 1d on 10,730; mean absolute 1-day move 1.83%.
- **Access:** attached to the rows of `/news/ticker/{symbol}`, `/news/threads/{id}` and its timeline.
- **Consumers:** initial-analysis (through the ticker route). Coverage is 31% because only articles whose ticker was requested get a row (October 12%, earlier months 25-45%).
- **Verdict:** `used well`, but incomplete by design (DA-N10).

### N7 Ticker reference  `ticker_reference` (63,871) and `data/news/tickers.csv`
- **Producer:** seeded from the CSV (`ticker_db.py`). **Consumer:** the ticker extractor inside the enrichment (name and alias matching). Internal only. **Verdict:** `used well` (internal).

### N8 Feed health  `feed_health` (22 feeds)
- **Producer:** the poller after each feed fetch. **Format:** last success/failure, fail streak, total polls and failures, mean latency, last error.
- **Access:** `GET /news/feeds` (config route). **Consumers:** none found; the Telegram status ping calls only the service root. One feed, `ap_top_news`, has failed 252 of 252 polls with `http_403` (DA-N2).
- **Verdict:** `no reader`; and the one real signal in it (a dead feed) is not alerted anywhere.

### N9 Backfill status  `backfill_status` (50) / N10 Settings  `vinu_settings` (12) / N11 Watchlist  `watchlist_tickers` (50)
- **Producers/consumers:** the service itself and the UI-style config routes (`/news/backfill/status`, `/news/settings`, `/news/watchlist/tickers`). The watchlist is shared with the stock-price service (`data/shared/watchlist.json`). Poll counters live in `vinu_settings` and are served by `/news/poll/status`.
- **Verdict:** `used well` (control data).

## Where news reaches a decision

news -> initial-analysis angles (`news_price_causality`, `shock_personality`, `drawdown_deep_dive`) -> stored angle rows -> research (`angle_context.compact_news_causality`: granger, correlation, news-volume correlation) -> strategy ideas in the LLM prompt. Also -> agent trade plan text and agent memory.

News does **not** reach the daily allocation, the live scheduler, the order guard or the breaker. See DA-N9.
