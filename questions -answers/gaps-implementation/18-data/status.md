# Status - 18-data

Date: 2026-09-09
State: doing (provider order done, PIT/gap pending)
Owner: agent build
Doing: failover order done. Next PIT test + gap scan backfill.
Done:
- registry.py: us_equity alpaca,polygon,tushare,yahoo + VINU_PROVIDER_ORDER env override.
Bugs found while implementing: test_api health providers permission error pre-existing, 13 green.
Other files touched:
- vinu-components/vinu-stock-price/vinu_stock/providers/registry.py:23
Next: PIT as-of join test + gap scan backfill.
Done2:
- models.py lineage_hash + loop.py data_hash per run, 74 green (freeze.py already exists).
