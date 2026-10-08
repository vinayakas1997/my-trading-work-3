# Data audit: vinu-screener

Checked 2026-10-08 on the running stack (`screener-api`, port 8095; databases `screener_rules.db`, `screener_rankers.db`, `screener_ranker_snapshots.db`, `screener_ranker_churn.db`, plus a watch-history audit store).

## What triggers it
- **Ranker scheduler:** every active ranker runs when its `interval_sec` is due. The one ranker (`core_starter`) runs every 86,400 s; last run 03:21 UTC today.
- **Rule scan (condition alerts):** `ScanMonitor` polls active rules every `interval_sec`. There are no rules.

## Data items

### R1 Ranker definition  `rankers` (1 row: `core_starter`)
- **Format:** JSON per ranker: universe (50 symbols), factors (momentum_short 10-day, momentum_medium, rsi_extreme_penalty, with weights), `top_n` 20, hard filter (min price 5, min dollar volume 1,000,000), `interval_sec`.
- **Access:** `GET/PUT/DELETE /screener/rankers`, `/rank`, `/enable`, `/disable`. **Consumers:** the scheduler; script `sync_universe.py`. **Verdict:** `used well` (control data). Seeded at start by `seed-default`.

### R2 Ranking snapshot  `ranker_snapshots` (1 row per ranker, overwritten each run)
- **Format:** `ranker_id, generated_at, top_json` (up to 20 entries: symbol, factor_score, risk_penalty, concentration_penalty, final_score, risk_flags, fields incl. price/volume/dollar_volume/data_stale), `trace_json` (stage counts), `rejected_json` (sample rejections).
- **Access:** `GET /screener/rankers/{id}/latest`.
- **Consumers (found in code):** agent planner worker (`fetch_screener_top_tickers`: the top-10 symbols decide which tickers get a trade plan; reads symbols only, not scores), agent Telegram channel, research `fetch_screener_rank_percentile` (a size tilt, but it only runs when `screener_ranker_id` is set in research, and it is not set, so it is inert), reflection `screener_agreement` (via churn), script `sync_universe.py`.
- **Not reaching:** portfolio, live scheduler, guards. The ranking does not influence sizing or entry today.
- **What was found in the data:** the latest snapshot ranked **20 of the 50** universe symbols. The trace says `hard_filter before 20`. The log shows why: at 03:24 and 03:25 two of the three 20-symbol candle chunks "timed out", so 30 symbols were never scored, and the snapshot carries no note that the universe was cut. Of the 20 that were ranked, 18 have a negative final score (META +0.07, ABBV 0.0, then -0.03 down to -0.97), yet all 20 are called "top".
- **Verdict:** `used` by the planner, but `wrong` when partial (DA-R1) and `single snapshot` (history overwritten, DA-R2).

### R3 Churn events  `ranker_churn_events` (106 rows)
- **Format:** `ranker_id, symbol, kind (entered|exited), at, from_rank, to_rank`. Example: TMO exited from rank 15.
- **Access:** `GET /screener/rankers/{id}/churn`. **Consumers:** reflection `screener_agreement` (does the pipeline independently agree), nothing else.
- **Verdict:** `single use`. Churn from a partial run (R2) is false churn: symbols "exit" because they were never fetched.

### R4 Rules  `rules` (0 rows) and watch history `fired_watches`
- **Format:** a rule is a condition tree with an interval; each firing is audited.
- **Access:** `/screener/rules/*` incl. `dry-run` and `history`. **Consumers:** none (there is nothing to consume). **Verdict:** `empty`: the whole condition-alert half of the screener has never been used (DA-R3).

## Where the screener reaches a decision
screener top-N -> agent planner (which tickers are planned) -> trade plans. Nothing else.
