# chronos — Timing

## Measured baseline (container, 4 CPU / 8GiB, synthetic 512 bars)

| Metric | Value |
|---|---|
| Model | amazon/chronos-t5-large (710M params) |
| dtype / device | torch.float32 / cpu (`chronos/compute.py:72`) |
| Context | 512 bars (`MIN_OBSERVATIONS`, `chronos/compute.py:45`) |
| Load time (first call) | **89.98 s** |
| Peak load memory (tracemalloc) | 220.7 MB (excludes torch tensors; real RSS higher) |
| Repeat 1 | 34.84 s |
| Repeat 2 | 39.36 s |
| Repeat 3 | 38.02 s |
| **Repeat average** | **37.41 s** |
| num_samples | 64 (`chronos/compute.py:122`) |

## What this means
- Model load is a one-time ~90s per process (cached via `_PIPELINE_CACHE`).
- Every real forecast call costs ~37s on CPU. A backtest with walk-forward steps calls this repeatedly → the dominant time sink.

## Notes
- Documented `~14s/call` in the module docstring was an earlier benchmark; current measurement is 37s (likely larger context/model config or differing load). Treat the new numbers as authoritative.
- `_PIPELINE_CACHE` keyed by CHECKPOINT means multiple tests in one process reuse the loaded pipeline (only one load per process).
