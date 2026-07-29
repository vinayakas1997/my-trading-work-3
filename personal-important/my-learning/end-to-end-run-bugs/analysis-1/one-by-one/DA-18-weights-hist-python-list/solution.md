# DA-18 🟡 `weights_hist` Stored as Python List (3-4× Memory Overhead)

**Component:** `vinu-simulator`
**Files Changed:** `simulator.py`

## Problem

On every simulation step, `w.tolist()` converted numpy arrays to Python lists. Python lists of floats consume 3-4× more memory than numpy arrays of the same shape, and conversion overhead accumulated across thousands of steps.

Two locations:
1. `simulator.py:267` — `weights_hist.append(w.tolist())` in `WeightSimulator.run()` 
2. `simulator.py:434` — `self._weights_history.append(w.tolist())` in `SimulatorEnv.step()`

## Fix

Store numpy arrays directly and use `np.stack()` at the end to build the DataFrame:

```python
# BEFORE
weights_hist: list[list[float]] = []
...
weights_hist.append(w.tolist())
...
weights_history_df = pd.DataFrame(weights_hist, index=total_calendar, columns=common_tickers)

# AFTER
weights_hist: list[np.ndarray] = []
...
weights_hist.append(w)
...
weights_history_df = pd.DataFrame(np.stack(weights_hist), index=total_calendar, columns=common_tickers)
```

Same pattern applied to `SimulatorEnv._weights_history`.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `simulator.py:125,267,271` | 3 | Store numpy arrays in `WeightSimulator.run()`; use `np.stack` for DataFrame |
| `simulator.py:321,434` | 2 | Store numpy arrays in `SimulatorEnv` |

## Verification

92 simulator tests pass (0 failures), including `TestWeightSimulator` and `TestSimulatorEnv` integration tests.
