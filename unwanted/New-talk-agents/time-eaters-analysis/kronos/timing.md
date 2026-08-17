# kronos — Timing

## Measured baseline (container, 4 CPU / 8GiB, synthetic 512 bars)

| Metric | Value |
|---|---|
| Model | NeoQuasar/Kronos-base (finance-specific TSFM) |
| dtype / device | default / cpu (`kronos/compute.py:117-118`) |
| Context | 512 bars |
| Load time (first call) | **20.59 s** |
| Peak load memory (tracemalloc) | 77.5 MB (excludes torch tensors) |
| Repeat 1 | 11.81 s |
| Repeat 2 | 13.67 s |
| Repeat 3 | 12.69 s |
| **Repeat average** | **12.72 s** |

## What this means
- **Second-worst time eater** after chronos (12.7s/call vs chronos 37s).
- One-time ~21s load per process.
- Finance-specific model (better signal than chronos) but costly on CPU.

## Notes
- Kronos tokenizer + model loaded separately (`kronos/compute.py:117-118`).
