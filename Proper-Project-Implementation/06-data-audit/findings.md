# Data audit findings

Running list. Status is `FIXED` (problem-log entry and guard test), `OPEN` (reason given) or `QUESTION` (needs a decision from the user, nothing invented).

## news (pilot, 2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-N1 | wrong shape | The news service answers `{"count", "data": [...]}` with unix-second times. Two agent readers (`memory/sync_service.py` `sync_news`, `tools/trade_plan_tool.py` `_fetch_news`) looked for `results`/`articles`, so they saw "no articles" for every ticker: the agent's memory never held news and every trade plan said no news. Had they seen articles, the plan's date slice (`[:10]` on an integer) would have crashed. Their tests mocked a bare list. | FIXED: problem-log P63, guard `vinu-agent/tests/test_news_payload_shape.py` |
| DA-N2 | dead source | Feed `ap_top_news` has failed 252 of 252 polls with `http_403`. Nothing reads `feed_health`, so nobody is told. | OPEN: see problem-log O24 |
| DA-N3 | thin data | 54,932 of 55,156 articles (99.6%) come from one provider (Benzinga). The 11 other sources give 224. No tier-1 source (Fed, SEC and similar) appears in the articles although their feeds poll fine. Last poll: 673 leads, 16 kept after the filter. | QUESTION: is the filter meant to keep this little? (O24) |
| DA-N4 | computes nothing | Clustering gives 55,156 clusters for 55,156 articles; threads hold one article in 99.6% of cases. With one source there are no duplicates to group. `story_threads` and `thread_daily_snapshots` (112k rows) have no reader. | OPEN (O24): fine while a single source dominates; becomes useful with more sources |
| DA-N5 | empty by design | `finbert_score`/`finbert_label` are empty on all articles (the models container is dormant). The `news_price_causality` significance model lists `finbert_score` as a feature, so that feature is always empty. | OPEN, by design (O24) |
| DA-N6 | computed then dropped | `news_price_causality/correlation.py` builds `avg_impact` from a field `impact_label` that the news service does not send (it sends `impact`, upper-case), so it is always 0, and nothing reads `avg_impact`. | OPEN, small (O24) |
| DA-N7 | no reader | `entities_json` (people, countries) is filled on 29% of articles; nothing reads it. | OPEN (O24) |
| DA-N8 | no reader | `ticker_daily_stats` (daily bullish/bearish/neutral count per ticker, 34,308 rows) and the routes `/news/stats/ticker`, `/news/high-impact`, `/news/latest`, `/news/watchlist/news`, `/news/threads/*` have no caller in any service. | QUESTION: should the screener or the portfolio read the daily mood? (O24) |
| DA-N9 | not used for decisions | News reaches strategy ideas only through the angle summaries in the research prompt, and the agent's trade-plan text. It does not reach the daily allocation, the live scheduler, the guards or the breaker. The `get_news` tool exists but no agent definition names it. | QUESTION: where should news be allowed to act? (O24) |
| DA-N10 | partial | Price reaction exists for 31% of articles (only for tickers that were requested), takes `tickers[0]` rather than the dominant ticker, and `dominance` is returned but unused. | OPEN, small (O24) |
| DA-N11 | wrong source of rows | The agent's two readers used `/news/search` (relevance order), so the plan's news section for AAPL showed headlines from 2023 and 2024. | FIXED with DA-N1 (P63): they use the newest-first ticker route |
