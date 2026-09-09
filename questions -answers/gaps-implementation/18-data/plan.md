# Plan - 18 Data Pipeline

Goal: Trusted data: PIT + gap fill + failover first.

Files touched:
- `vinu-components/vinu-news/config.py:14` poll 600s tiers.
- `vinu-components/vinu-stock-price/live/ingest_cycle.py:46`, `catalog/store.py:226`, `query/engine.py:5` ingest/dedupe.
- `vinu-components/vinu-initial-analysis/quarters.py:1` immutable window + has_existing_run.
- Price client as-of join PIT test.
- Freeze manifest `vinu-infra/` + RunLog data_hash.

Steps:
1. PIT test + gap scan backfill + provider order alpaca,polygon,tushare.
2. Handler + freeze + pairlist vol filter.
3. Retention 1m 90d + lag alerts 3x.
4. Image slim CPU 3.5GB last.

Knobs: PIT, GAP_FILL, PROVIDER_ORDER, FREEZE, RETENTION, LAG_ALERT, MODELS_DIR (see 10).
Acceptance: no leak, hole filled no double, failover on lag, hash matches.
