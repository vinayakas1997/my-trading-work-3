# Angle 04: Alpha Factor Zoo — Bugs

## Bug 1: gtja191 Preset Not Registered in HTTP API
- **Endpoint**: `POST /requests` with `preset: "gtja191"`
- **Error**: `400 {"detail":"Unknown preset: gtja191"}`
- **Root Cause**: Only 11 presets are registered in the HTTP API (`/presets`): alpha101, alpha158, alpha360, 8 TA packs. gtja191 (191 factors) exists in the Python registry but has no corresponding HTTP preset registration.
- **Impact**: Cannot compute gtja191 factors via REST API. Must use Python API instead.
- **Workaround**: Use `from vinu_features.compute.alpha_factors.gtja191.alpha_001 import compute` directly, or `factor_expressions.compute_expression("gtja191_001", panel)`.

## Bug 2: qlib158 Preset Not Registered in HTTP API
- **Endpoint**: `POST /requests` with `preset: "qlib158"`
- **Error**: `400 {"detail":"Unknown preset: qlib158"}`
- **Root Cause**: Same as Bug 1 — qlib158 (154 factors) has no HTTP preset registration. Note: `alpha158` is a different preset (158 factors from a different source).
- **Impact**: Same as Bug 1.
- **Workaround**: Compute qlib158 factors individually via Python API.

## Bug 3: Individual Alpha Factor Names Fail via HTTP API (FIXED)
- **Endpoint**: `POST /requests` with `features: ["ALPHA101_001"]`
- **Error**: `400 {"detail":"Unknown feature: alpha101_001"}`
- **Root Cause**: The API lowercases input feature names before lookup, but the internal alpha name sets from `_alpha_name_sets()` stored uppercase names. Case mismatch caused all alpha features to be rejected.
- **Fix**: Changed `if name in a158 or name in a360 or name in a101:` to `if name.upper() in a158 or name.upper() in a360 or name.upper() in a101:` in `validate_feature_name()` — registry.py:69
- **Impact**: Fixed. Individual alpha factor names (alpha101_001, KMID, CLOSE0) now work via the features API.

## Bug 4: Fundamental Factors Not Registered
- **Subject**: `fundamental_roe`, `fundamental_asset_growth`
- **Error**: `Registry.get("fundamental_roe")` returns `None`
- **Root Cause**: The 4 `fund/` directory factors use a naming convention (`fund_*`?) that doesn't match the registry's scanning pattern. Files exist on disk but `fund` is not recognized as a family prefix.
- **Impact**: 4 fundamental factors (ROE, asset growth, etc.) are invisible to the registry and HTTP API.
- **Workaround**: Import factor module directly from `alpha_factors/fund/` directory.

## Bug 5: gtja191 Equity China Universe Mismatch
- **Subject**: gtja191 factors tagged `universe: equity_cn`
- **Issue**: All gtja191 factors are designed for China A-shares. Computing them on US equities (AAPL, MSFT, TSLA, NVDA) may produce spurious or meaningless results due to different market microstructure (T+1 settlement, price limits, etc.).
- **Impact**: Results may not be valid despite successful computation.
- **Notes**: This is a design limitation rather than a code bug. Test on China A-share data if gtja191 factors are needed.

## Bug 6: No Bulk Factor Metadata API
- **Endpoint**: Missing — no REST endpoint exposes factor metadata (theme, columns_required, decay_horizon, formula, universe)
- **Workaround**: Use Python API (`Registry.list_alphas()` and iterate) to extract metadata programmatically.
