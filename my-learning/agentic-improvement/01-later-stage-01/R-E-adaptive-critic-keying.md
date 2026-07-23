# R-E: Adaptive Critic — Normalize Suggestion Keys

## Bug

`_filter_ineffective_suggestions()` in `loop.py:933-943` keyed effectiveness tracking on the exact rendered suggestion string. But critic suggestions embed live numbers that differ every iteration:

```
Iter 3: "Sharpe 1.23 is not statistically significant"
Iter 4: "Sharpe 0.89 is not statistically significant"
```

These map to different dictionary keys despite being the same conceptual suggestion — so `_suggestion_results` rarely accumulates more than one observation per key, and the "learn what critic advice doesn't work" feature (P4's headline claim) is mostly inert.

## Fix

Added `_normalize_suggestion_key()` static method:
1. Strip all numbers (digits and decimals) — `re.sub(r"\d+\.?\d*", "", s)`
2. Collapse whitespace, lowercase, trim
3. Cap at 80 chars

Both the storage side (`loop.py:339-344`) and the lookup side (`_filter_ineffective_suggestions`) now use the normalized key, so identical conceptual suggestions accumulate observations across iterations.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py` | ~8 | Added `_normalize_suggestion_key` static method |
| `loop.py` | ~1 | Storage: use `_normalize_suggestion_key(s)` as dict key |
| `loop.py` | ~1 | Lookup: use `_normalize_suggestion_key(s)` for dict lookup |
