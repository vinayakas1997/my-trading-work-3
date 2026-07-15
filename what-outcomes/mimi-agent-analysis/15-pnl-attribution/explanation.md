# Pnl Attribution

## What This Angle Studies
Decomposes portfolio PnL into components: Core PnL, Noise trades, Early exit, Late exit, Overtrading.

## Results
PnL decomposition works: total=0.25, core=-0.06, noise=0.00. The core PnL (excluding top/bottom quartile trades) can be negative even when total PnL is positive, indicating noise trades contribute. Per-exit-reason and per-symbol attribution logic exists in codebase.

## Execution Time
~0.02s

### Bugs Found
None.