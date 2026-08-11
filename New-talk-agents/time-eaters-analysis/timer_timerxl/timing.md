# timer_timerxl — Timing

## Measured baseline (container, 4 CPU / 8GiB, synthetic 512 bars)

| Metric | Value |
|---|---|
| Model | thuml/timer-base-84m (84M params) |
| dtype / device | float32 / cpu (`timer_timerxl/compute.py:162-166`) |
| Backend | **pretrained** ✅ (after HF_HOME fix — see below) |
| Load time (first call) | 27.00 s |
| Peak load memory (tracemalloc) | 214.2 MB (excludes torch tensors) |
| Repeat 1 | 0.05 s |
| Repeat 2 | 0.07 s |
| Repeat 3 | 0.02 s |
| **Repeat average** | **0.05 s** |

## Summary
- **Not a time eater once fixed.** Real Timer model loads and forecasts in ~0.05s/call.
- Load is one-time ~27s per process (cached via `_MODEL_CACHE`).
- This is the **fastest** of the 4 measured models (84M params, single forward pass).

## Before the fix
Measured 0.44s/call was the **statistical proxy**, not the real model.
`fallback_reason` was `OSError(30, 'Read-only file system')` — real model failed to load.
See optimizations.md for the fix that was applied.
