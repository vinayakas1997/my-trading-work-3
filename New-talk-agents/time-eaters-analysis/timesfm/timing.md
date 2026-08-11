# timesfm — Timing

## Measured baseline (container, 4 CPU / 8GiB, synthetic 512 bars)

| Metric | Value |
|---|---|
| Model | google/timesfm-2.5-200m-pytorch (200M params) |
| dtype / device | default / cpu (`timesfm/compute.py:66-77`) |
| Context | up to 1024 (`MAX_CONTEXT`, `timesfm/compute.py:46`) |
| Load time (first call) | **11.56 s** |
| Peak load memory (tracemalloc) | 76.5 MB (excludes torch tensors) |
| Repeat 1 | 0.53 s |
| Repeat 2 | 0.53 s |
| Repeat 3 | 0.51 s |
| **Repeat average** | **0.52 s** |
| Horizon | 5 (`HORIZON`, `timesfm/compute.py:41`) |

## What this means
- **Not a time eater.** 200M model, single forward pass (not 64 sampled paths like chronos) → ~0.5s per call.
- Load is one-time ~12s per process (cached via `_MODEL_CACHE`).

## Verdict
timesfm contributes negligible runtime to the test suite. No optimization needed for speed.
