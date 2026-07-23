# R-D: Stock Characterization — Pass Computed Metrics to LLM

## Bug

`_characterize_stock()` in `loop.py:822-867` extracted RSI, ADX, and ATR values from `_feature_snapshot` for the human-readable profile (lines 838-852) but only passed `symbol` and `angle_context` to the LLM `characterize_stock()` call (line 864). The function signature in `llm.py:330-337` accepted `volatility`, `rsi_percentiles`, `ar1`, and `adx` parameters — but they were never populated.

The LLM characterization was therefore much thinner than its prompt schema implied, missing the actual numerical signals the system had already computed.

## Fix

Forward `volatility` (from `trend_lifecycle`) and `adx` (from `_feature_snapshot`) to the LLM call. `rsi_percentiles` and `ar1` are still not passed — those require distribution data the current feature snapshot doesn't provide.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py` | 861-868 | Extract `vol_val`, `adx_val` from already-loaded data, pass to `characterize_stock()` |
