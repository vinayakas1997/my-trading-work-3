# Status - 18-data

Date: 2026-09-09
State: done (order+lineage+refill+PIT)
Owner: agent build
Doing: failover order done. Next PIT test + gap scan backfill.
Done:
- registry.py: us_equity alpaca,polygon,tushare,yahoo + VINU_PROVIDER_ORDER env override.
Bugs found while implementing: test_api health providers permission error pre-existing, 13 green.
Other files touched:
- vinu-components/vinu-stock-price/vinu_stock/providers/registry.py:23
Next: none, order+lineage+refill+PIT closed (failover first already via registry).
Done4:
- test_pit.py: as-of excludes future + indicators match slice, 2 green.
Done2:
- models.py lineage_hash + loop.py data_hash per run, 74 green (freeze.py already exists).
Done3:
- year_job.py: gap refill queue same year, merge no double, 3 green.
