# kronos — Optimizations

## Option 1: Load model in bfloat16
`kronos/compute.py:117-118` — pass `torch_dtype=torch.bfloat16` to `Kronos.from_pretrained(...)`.
- Halves memory, faster CPU matmul on AVX-512 (i5-13450HX).
- **Expected:** ~12.7s → ~6-8s/call. **Risk:** LOW. **Effort:** minutes.

## Option 2: Cross-process model reuse
Same sidecar approach as chronos Option 4 — load once, serve forecast calls. Kills the 21s per-process load.

## Option 3: Reduce num_samples / forecast horizon if configurable
Kronos uses its own sampling; check `compute.py` for a samples parameter. Fewer samples = fewer passes.

## Recommendation
1. Apply Option 1 (bf16) → re-measure.
2. If backtests still dominate, add Option 2.
