# Data Pipeline Upstream - Flow + Gaps + Repos Extras + Top 2 (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `18`. Related: `05`, `17`.
Status: Data step closed with 4 gaps + 3 extras + 2 top = 9 total. Code steps ready to build next, no code changed yet in this doc.

---

## How data flows today (4 goods)

1. News 8080 poll 600s, tiers 1 to 4, workers 8. File `vinu-news/config.py:14`. Watchlist sync via shared file `/shared/watchlist.json`. Good.
2. Stock 8081 poll 60s, 1m ingest always raw, parquet store, `ingest_log` per symbol bars added + ok or error. Files `vinu-stock/live/ingest_cycle.py:46`, `catalog/store.py:226`. Query aggregates to 5min, 1H, 1D. Good.
3. Features 8082 catalog 24 indicators + bundles full_ta 32, mean_reversion, momentum, alpha101. Good for look. Backtest-safe only 10 sma, rsi, macd, adx, vol. Mismatch noted in `05` file, not new here.
4. Initial 8083 tier2 quarterly immutable `[2022-01-01, period-end)`. File `vinu-initial-analysis/quarters.py:1`. End stable per quarter, dedupes via `has_existing_run`. Tier3 v1 fetch for Full 2022. 28 angles, 1D 27/27, 1H 28/28, 15min 28/28. GPU 8g 4cpu. Good. 3 formats stored always.

---

## 4 gaps in data (inefficiencies)

### 1. No PIT guarantee
Qlib PIT contract pending Row 15. Price revision, split, dividend can leak future into past. `price_client` pagination `while cursor < to_ts` exclusive good, but no as-of join test.
Fix: PIT test asserts as-of join, no leakage across embargo. Same pattern as Qlib `test_pit`. Small.
Knobs: `VINU_DATA_PIT_ENABLED=true`.
Status: Open. Do first with 2-3. Trust.

### 2. Duplicate bars + gap holes
Known issue 2 duplicate live-ingest shards. No auto gap-fill job after provider outage.
Fix: nightly gap scan + backfill trigger + dedupe on write. Small job. Reuse `catalog/log_ingest` ok and error rows to find holes.
Knobs: `VINU_DATA_GAP_FILL_ENABLED=true`, `VINU_DATA_GAP_SCAN_HOURS=24`.
Status: Open. Do first. Trust.

### 3. Provider failover order unclear
Alpaca default, Polygon, Tushare, FMP keys exist in `.env-example`. No pinned order Alpaca to Polygon to Tushare on fail.
Fix: pin order + per-provider lag metric + auto switch on fail or lag over 3x poll. Small config + 1 switch function.
Knobs: `VINU_STOCK_PROVIDER_ORDER=alpaca,polygon,tushare`, `VINU_STOCK_FAILOVER_LAG_MULT=3`.
Status: Open. Do first. Trust.

### 4. Image 6.52GB + compute 3600s poll
Torch + transformers + chronos + timesfm. Code 3.5MB, deps 5GB. Starts slow, compute poll hourly. Q39-40 discussed keep dynamic, slim image.
Fix: slim CPU torch 3.5GB + warm models host + cache, keep GPU for kronos only. Medium infra.
Knobs: `VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC=3600` kept, `VINU_MODELS_DIR=/models` kept.
Status: Open. After trust green. Infra.

---

## 3 advanced from other repos on top

### 5. Qlib handler + Arctic + PIT DB
Source `03-per-repo-deep-dive/qlib-PIT-RD-Agent.md:20`. Handler processor + Alpha360 angle example + as-of join no leakage test.
Adopt PIT test pattern + handler for features pipeline. Low. Same as gap 1 fix, plus handler.
Status: Open.

### 6. Nautilus catalog + lineage freeze
Source `nautilus-fills-catalog.md:21`. Parquet catalog versioning + hash `data/news:stock:features` + contamination check. Adopt freeze manifest Row 21.
Where: `vinu-infra/` + `RunLog`. Hash inputs per run, store `data_hash` on artifact already planned `09`. Medium, after PIT.
Status: Open.

### 7. Freqtrade pairlist vol filter before gate
Source `freqtrade-leak-guard.md:22`. Prune illiquid by vol and volume before screener LLM cost. Same as `08` pairlist. Low. Data side + research side same knob.
Knobs: `VINU_SWEEP_PAIRLIST_ENABLED`, `VINU_SWEEP_MIN_VOLUME` kept from `10`.
Status: Open.

---

## 2 more on top (added so nothing missed)

### 8. Retention + pruning policy
Parquet grows forever 2022 to now per ticker per interval. No prune rule. Same shape as ledger retention undecided.
Fix: keep raw 1m 90 days, aggregate 1H and 1D forever, prune news bodies 1 year keep embeddings. Small policy + nightly job. Prevents disk full.
Knobs: `VINU_DATA_RETENTION_1M_DAYS=90`, `VINU_DATA_RETENTION_NEWS_DAYS=365`.
Status: Open. Small. Include now.

### 9. Freshness lag alerts
Ingest lag silent today. Stock 60s stops 30 min, screener still uses stale 27/27 summary. No SLA.
Fix: lag metric per service + alert if `now - last_bar > 3x poll`. News 600s lag 30min alert, stock 60s lag 5min alert, features lag 10min alert. Reuse significance worker delivery, no new channel. Small.
Knobs: `VINU_DATA_LAG_ALERT_ENABLED=true`, `VINU_DATA_LAG_MULT=3`.
Status: Open. Small. Include now.

---

## Knobs full list for data (add to 10 later build)

- Poll: `VINU_NEWS_POLL_INTERVAL_SEC=600`, `VINU_STOCK_POLL_INTERVAL_SEC=60`, `VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC=3600` kept.
- Window: `VINU_STAGE1_START_DATE`, `VINU_TIER2_PERIOD_MONTHS=3` kept.
- Trust: `VINU_DATA_PIT_ENABLED`, `VINU_DATA_GAP_FILL_ENABLED`, `VINU_DATA_GAP_SCAN_HOURS`, `VINU_STOCK_PROVIDER_ORDER`, `VINU_STOCK_FAILOVER_LAG_MULT`.
- Freeze: `VINU_DATA_FREEZE_ENABLED` (Row 21), pairlist kept from `10`.
- Keep: `VINU_DATA_RETENTION_1M_DAYS`, `VINU_DATA_RETENTION_NEWS_DAYS`, `VINU_DATA_LAG_ALERT_ENABLED`, `VINU_DATA_LAG_MULT`.
- Models: `VINU_MODELS_DIR=/models` kept. Image slim separate infra task.
- Future timeframe: `VINU_SWEEP_INTERVALS=1d,1H,15min` drives compute + sweep, 3 formats 9 per ticker now. New interval appears after ingest has bars.

---

## Order to build (trust first, closed 9)

1. PIT test + gap fill + failover. 1-3 together. Data trust. Small jobs. Do first.
2. Qlib handler + freeze + pairlist. 5-7 together. After 1 green. Lineage + cost save.
3. Retention + lag alerts. 8-9 together. After 2 green. Disk + SLA.
4. Image slim. Step 4 last. Infra. After trust green.
5. Test: PIT no leak, gap scan fills hole dedupe no double, failover switches on lag, freeze hash matches, retention prunes 1m keeps 1D, lag alerts fire on stall.

After 1-5, data done. Next is 5 portfolio inside + 6 learning. Different docs.

---
Link: Portfolio inside 4 gaps + 3 extras + 4 regimes is in `19-portfolio-inside.md`. 18 -> 19 = data -> portfolio closed.

---

## All covered proof (nothing missed for data)

- News `config.py:14` poll tiers workers, shared watchlist path covered.
- Stock `live/ingest_cycle.py:46`, `catalog/store.py:226` log, `settings/store.py:10` poll 60, `server/routes_config.py:160` trigger, `query/engine.py:5` dedupe known issue 2 covered gaps 2-3.
- Features catalog 24 + bundles covered, backtest-safe 10 mismatch kept in `05`.
- Initial `quarters.py:1` immutable window + `has_existing_run` dedupe + tier3 v1 + 28 angles 27/27 1D 28/28 1H + GPU covered.
- Secrets provider keys `.env-example` + `secrets_loader` kept, no new.
- Repos mapped: Qlib PIT handler 5 here, Nautilus freeze 6 here, Freqtrade pairlist 7 here. No new repo needed.
- Ledger `inefficiencies-A-J.md:D` cache built kept, J double fetch built kept. C recipe fallback open kept in `07`. I secrets built kept.
- Slices `04` A1-A3 + B kept. Row 15 PIT here step 1, Row 21 freeze here step 6.
- 09 top3, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full, 14 storage full, 15 monitor closed, 16 broker closed, 17 UI closed kept. 18 closes data.
