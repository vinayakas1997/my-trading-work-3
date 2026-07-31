# vinu-portfolio — Test Log

**Status:** Not started

## What will be tested

- `vinu-portfolio historical-simulate --days N` against real data — the
  first real (non-synthetic) exercise of this CLI, built during the
  Step 07 audit work.
- `GET /portfolio/daily-allocation` and `/daily-game-plan` combining all
  3 strategies with regime-alignment tilt applied.
- `GET /portfolio/risk/status`.
- Readiness score behavior on real data (does it correctly reflect when
  regime/equity/strategy data is actually available vs. missing).

## Expected output

- `historical-simulate` produces a non-empty `SimulationResult` with real
  numbers — no exceptions, no NaN weights.
- Weights sum to 1.0 (± float tolerance) on every simulated day — this was
  already verified against synthetic data in
  `vinu-portfolio/tests/test_historical_simulation.py`; this test
  confirms it holds for real data too.
- Readiness score reflects the documented scope limit: only risk-parity +
  regime-alignment tilt are replayed historically, so the score should
  not falsely claim full-system coverage for historical runs.
- `daily-game-plan` output is consistent with what the `vinu-agent` skill
  docs (`agent-self`, `daily-allocation`, `live-safety`) describe the
  agent as expecting to read.

## Bug / Fix Log

_Nothing logged yet — testing has not started._
