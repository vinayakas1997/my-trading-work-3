# kronos — Bottlenecks

## 1. CPU inference of a real transformer
Kronos-base is a finance-pretrained foundation model. 512-token context autoregressive forecast on CPU = ~12.7s/call. This is the model's intrinsic cost on CPU.

## 2. dtype float32
`kronos/compute.py:117-118` loads tokenizer + model via `from_pretrained` with default dtype (float32) on CPU. bf16 would halve memory and speed matmuls on AVX-512.

## 3. Load cost per process
In-process caching only (`_MODEL_CACHE` in other angles; kronos relies on module-level cache in `compute.py`). Each new Python process re-does ~21s load.

## 4. Backtest walk-forward multiplication
`test_kronos_backtest.py` / `backtest.py` loop `_forecast`-style calls → 12.7s × steps.

## Priority
1. bf16 dtype (easy, ~2× speed)
2. cross-process model reuse (kills 21s loads)
