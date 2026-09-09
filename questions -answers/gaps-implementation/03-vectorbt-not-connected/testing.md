# Testing - 03-vectorbt-not-connected

Command:
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid"
- VINU_SWEEP_USE_VECTORBT=false python3 -m pytest vinu-research/tests/ -q -k "sweep or grid"
Expected: 35 passed both modes, order preserved, no regression.
Actual: 35 passed true + 35 passed false.
Status: green.
Proof log: build output 2026-09-09 both modes green.
Note: 20pts 10s needs live sim timing, unit proves logic + rollback.
