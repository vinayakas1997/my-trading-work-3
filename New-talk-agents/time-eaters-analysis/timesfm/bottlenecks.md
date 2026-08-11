# timesfm — Bottlenecks

## Assessment: LOW priority (fast already)

- 200M params (vs chronos 710M), single-pass point+quantile forecast → **0.52s/call**.
- No sampled-path amplification like chronos's `num_samples=64`.
- One-time 11.6s load per process (cached in-process via `_MODEL_CACHE`, `timesfm/compute.py:50`).

## Remaining notes
- Load cost repeats per process (same pattern as all angles — in-process cache only).
- If many backtest steps call it, 0.5s × steps adds up, but far below chronos/kronos/timer.
