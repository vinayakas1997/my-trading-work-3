# chronos — Optimizations

## Option 1: Reduce num_samples (biggest per-call win)
`chronos/compute.py:122` uses `num_samples=64`. Each sample is one autoregressive path.
- **64 → 20**: ~3× fewer paths. Quantile stability degrades slightly (p10/p90 noisier) but p50 remains stable.
- **Trade-off:** p10/p90 confidence bands become less smooth; the `p10 <= actual <= p90` hit-check becomes noisier.
- **Risk:** LOW (config-only change). **Effort:** minutes.

## Option 2: Load in bfloat16 on CPU
`chronos/compute.py:72` `dtype=torch.float32` → `torch.bfloat16`.
- Halves memory (710M × 2 bytes ≈ 1.4GB), and bf16 matmul is faster on AVX-512 (i5-13450HX supports it).
- **Risk:** bf16 precision loss on CPU is minor for 5-step forecasts. **Effort:** minutes.

## Option 3: Reduce context below 512
`MIN_OBSERVATIONS=512` (`chronos/compute.py:45`, fixed). Could drop to e.g. 256 — but this changes the angle's contract (model is designed for 512). **Not recommended** without an architecture decision.

## Option 4: Cross-process model reuse (kill the 90s loads)
`_PIPELINE_CACHE` is per-process. Options:
- A small long-lived model-server sidecar (e.g. torchserve / custom FastAPI) that loads once and serves forecasts.
- Or `--preload` one model at container start and fork workers.
- Big win for test suites (many processes) and API latency (first request per worker).
- **Risk:** new infra. **Effort:** medium.

## Option 5: Threads / cores
Torch intra-op threads follow `torch.get_num_threads()`. With `cpus: 4` the container gets 4, but the background `vinu-initial-compute --all --continuous` worker (`entrypoint.sh:4`) competes. During test runs it can be stopped to dedicate all 4 cores.

## Recommendation
1. Apply Option 1 (num_samples 20) + Option 2 (bf16) → expect ~37s → ~8-12s/call.
2. Re-measure and record in this folder.
3. If still slow: Option 4 (sidecar) as a follow-up.
