# Time Eaters Analysis

Per-model timing and optimization analysis for the vinu-initial-analysis ML angles.

## Purpose

Each ML/transformer angle loads real pretrained weights and runs inference on CPU. This folder tracks:
- **timing.md** — measured load time (first call) + per-call latency + peak memory
- **bottlenecks.md** — what is slow and why (device, dtype, model size, config)
- **optimizations.md** — concrete options to make it faster, with trade-offs

## Structure

| Folder | Angle | Model | Status |
|---|---|---|---|
| `chronos/` | chronos | amazon/chronos-t5-large (710M) | done — 37s/call, heaviest |
| `timesfm/` | timesfm | google/timesfm-2.5-200m-pytorch (200M) | done — 0.52s/call, fast |
| `kronos/` | kronos | NeoQuasar/Kronos-base | done — 12.7s/call |
| `timer_timerxl/` | timer_timerxl | thuml/timer-base-84m | done — 0.05s/call after HF_HOME fix |

More angles (tft, itransformer, dlinear, lstm, patchtst, lpatchtst, tips, cross_attention_gcn, moirai, moment, lag_llama) can be added as measured.

## Measurement method

Standard harness run in the `initial-analysis-api` container:
- Synthetic window of 512 bars (matches chronos min context)
- Record: first-call load time, 3 repeat per-call latencies, peak RSS
- Record baseline BEFORE any optimization, re-record AFTER each change

## Measured results (512 bars, container 4 CPU / 8GiB)

| Angle | Load (s) | Per-call (s) | Verdict |
|---|---|---|---|
| chronos | 89.98 | 37.41 | heaviest — 64 samples, 710M params |
| kronos | 20.59 | 12.72 | 2nd heaviest |
| timesfm | 11.56 | 0.52 | fast |
| timer_timerxl | 27.00 | 0.05 | fast (after HF_HOME fix) |

## Hardware context

- Host: 13th Gen Intel i5-13450HX, 10 cores / 16 threads, 31.7GB RAM
- Docker: 16 CPUs / ~15.5GB allocated
- Container: now `cpus: 4`, `mem_limit: 8g` (raised from 1 CPU / 1GB)
