# Plan - 25 Money Gate

Goal: Enforce 5 proofs + ladder + kills. Today 2/10, no fund.

Files touched (gate doc first, code after edge):
- Edge: `backtest_runner/prompt.md:53`, `comparison.py:19`, `pbo.py`, `sweep_grid.py`.
- Costs: `costs.py:73`, `execution.py:33`, `16` 9 steps.
- Sizing: `position_sizing.py:15`, `05-sizing`, `13` tail vol.
- Corr: `correlation_gate.py:34`, `service.py:347`, `19` sleeves.
- Exec: `orchestrator.py:486`, `order_guard.py:31`, `kill_switch.py`, `18` lag, `22` retry.
- Gate knobs + ladder stages + kills wiring.

Steps:
1. Gate doc + knobs + ladder + kills read-only. This file. No live change.
2. Build edge 1 prompt + top3 9 unlocks PASS. Then costs honest + tail vol + HALT exits before live10%.
3. Ladder auto paper->live10 30d->live50 60d->live100 on proofs + DD held + rated.
4. Tests: red blocks live, ladder up only green, kills allow exits.

Knobs: DEFLATED_MIN 0.95, HOLDOUT, PBO_MAX 0.5, MIN_TRADES 30, PAPER 10/5, DEGRADATION 0.5, NET_REQUIRED, STAGE paper/live10/live50/live100, OVERRIDE false (see 10).
Acceptance: 2/10 -> 5/10 paper green -> 7/10 live60d. Fund only on proof.
