# chronos — Bottlenecks

## 1. Model size on CPU
`chronos-t5-large` = 710M params. In float32 that is ~2.8GB just for weights. The container previously had `mem_limit: 1g` → guaranteed swap thrash. Now at 8GiB it fits, but forward pass on 1-4 CPUs is the hard floor.

## 2. dtype=float32 on CPU
`chronos/compute.py:72` loads with `dtype=torch.float32`. No bfloat16/float16, no quantization → 4 bytes/param and slower matmuls than bf16 on modern CPUs.

## 3. 64 sampled paths per call
`chronos/compute.py:122` runs `num_samples=64` → the autoregressive forecast samples 64 paths through a 710M-param T5. This multiplies inference cost ~64×.

## 4. Load cost per process
`_PIPELINE_CACHE` (`chronos/compute.py:53`) is in-process only. Each new Python process (each test file, each API worker restart) re-does the ~90s load. No cross-process/disk-persisted model server.

## 5. Backtest walk-forward multiplication
`test_chronos_backtest.py` and `backtest.py` call `_forecast()` repeatedly in a walk-forward loop → 37s × number of steps.

## Priority ordering
1. num_samples 64 → smaller (biggest per-call win)
2. bf16 loading (halve memory + faster)
3. cross-process model reuse (kill repeated 90s loads)
