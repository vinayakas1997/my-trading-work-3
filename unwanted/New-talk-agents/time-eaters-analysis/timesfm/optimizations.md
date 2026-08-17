# timesfm — Optimizations

## Verdict: NONE needed for speed
0.52s/call on CPU is already fast. Skip this angle unless profiling shows backtest loops dominate.

## If ever needed
- Reduce `MAX_CONTEXT` from 1024 (less input per call) — but that changes model operating config, not recommended.
- Cross-process model reuse sidecar (see chronos Option 4) would remove the 11.6s per-process load — only matters for many processes (test suite / worker restarts).
