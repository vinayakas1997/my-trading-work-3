# DA-10 🟠 Recipe Over-Computation in vinu-tools

**Component:** `vinu-tools`
**Files Changed:** `compute_alpha.py`, `catalog.py`, `registry.py`, `alpha101_benchmark.py`, `alpha158.py`, `alpha360.py`

## Problem

When any single alpha101 factor is requested (e.g., `ALPHA101_001`), `apply_indicators()` computes ALL 101 factors via `compute_recipe("alpha101_benchmark")` then discards 100 of them. Same for alpha158 (~158 factors) and alpha360 (360 factors).

Worst-case waste:
- alpha101: 99% (101 computed, 1 used)
- alpha158: ~99% (158 computed, 1 used)
- alpha360: 99.7% (360 computed, 1 used)

## Root Cause

`compute_alpha()` in `compute_alpha.py:20-26` iterated over all formulas unconditionally:

```python
fields, names = getter()          # ALL formulas
for expr, col in zip(fields, names):  # ALL evaluated
    out[col] = evaluate(expr, arrays)
```

The caller in `registry.py:353-370` only filtered AFTER computation:

```python
if any(n in a101 for n in expanded):
    cols = recipe_catalog.compute_recipe(rows, "alpha101_benchmark")  # ALL 101
    for n in expanded:
        if n in cols:  # only uses requested subset
            row[n] = cols[n][i]
```

## Solution

Added a `subset` parameter to `compute_alpha()`, `compute_recipe()`, and the 3 alpha recipe modules. When `subset` is set, only the requested formulas are evaluated.

### Changes

| File | Lines | Change |
|------|-------|--------|
| `compute_alpha.py:20` | +4 | Added `subset: set[str] \| None = None` param; filter fields/names before eval loop |
| `catalog.py:77` | +2 | Added `subset` param to `compute_recipe()`; pass to recipe's compute when set |
| `registry.py:353-366` | +3 | Compute `subset = {n for n in expanded if n in a101}` per recipe; pass to `compute_recipe()` |
| `alpha101_benchmark.py:58` | +1 | Accept `subset` param, forward to `compute_alpha()` |
| `alpha158.py:180` | +1 | Accept `subset` param, forward to `compute_alpha()` |
| `alpha360.py:52` | +1 | Accept `subset` param, forward to `compute_alpha()` |

### Flow (before vs after)

**Before:** Request `ALPHA101_001` → compute ALL 101 → discard 100 → return 1
**After:** Request `ALPHA101_001` → compute 1 → return 1

## Verification

69 vinu-tools tests pass (0 failures).
