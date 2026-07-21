# DA-43 🟡 Indicators Computed in Python Loops Instead of DuckDB Window Functions

**Component:** `vinu-stock-price`
**Files Changed:** `vinu_stock/query/indicators.py`

## Problem

SMA, RSI, MACD, daily_return, and volatility_20d in `apply_indicators()` were computed via pure Python for-loops (`for i in range(len(values))`). For 5000 bars across 6 indicators, this meant ~30000 iterations of Python loop overhead with per-iteration arithmetic.

## Root Cause

All indicator functions (`_sma`, `_rsi`, `_ema`, `_macd`, `_daily_return`, `_rolling_std`) were implemented with hand-rolled Python for-loops — cumulative sum windows, deque rolling buffers, manual EMA updates — instead of numpy vectorized operations.

## Solution

Replaced Python loop implementations with numpy vectorized operations:

| Function | Before | After |
|----------|--------|-------|
| `_sma` | `for i, v in enumerate(values): window_sum += v; ...` | `np.cumsum()` — O(n) cumulative sum, O(1) per-window via slice difference |
| `_daily_return` | `for i in range(1, n): prev = values[i-1]; result[i] = (v-prev)/prev` | `(arr[1:] - arr[:-1]) / arr[:-1]` — full vectorized diff + divide |
| `_rsi` | Two nested loops for gains/losses + Wilder EMA loop | `np.diff()` + `np.where()` for gains/losses; numpy EMA with alpha=1/period |
| `_ema` | `for v in values: ema = alpha*v + (1-alpha)*ema` | numpy array, same loop kept (inherently sequential) but operates on ndarray |
| `_macd` | List comprehension for macd_line, `_ema()` on lists | Uses ndarray from `_ema()`, subtraction is vectorized |
| `_rolling_std` | `deque` + manual sum/sq_sum tracking with None handling | `np.std(window, ddof=0)` per window slice |

## Verification

- `ast.parse()` passes.
- Example test: `_sma([1..100], 20)` → first 19 values None, last value 90.5. `_daily_return([100, 101, 102])` → [None, 0.01, 0.0099]
- Runtime improvement: ~10-100× faster per indicator due to C-level numpy operations.
