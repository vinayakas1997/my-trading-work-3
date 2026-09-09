# Testing - 18-data (order+lineage)

Command:
- python3 -m pytest vinu-stock-price/tests/ -q -k "provider or registry or fallback"
- python3 -m pytest vinu-research/tests/ -q -k "loop or model"
Expected: 13 + 74 passed, lineage hash per run.
Actual: 13 + 74 passed, hash 563fed6f94bd sample.
Status: green for order+lineage, red for PIT/gap pending.
Proof log: build output 2026-09-09.
Note: PIT + gap backfill pending separate.
