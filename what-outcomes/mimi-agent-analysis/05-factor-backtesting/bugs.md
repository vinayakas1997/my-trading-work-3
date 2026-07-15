# Angle 05: Factor Backtesting — Bugs

| # | Bug | Error | Root Cause | Fix | Status |
|---|-----|-------|------------|-----|--------|
| 1 | Hardcoded min_assets=10 blocks small universes | All metrics zero | `backtest_factor()` rejects any period with <10 valid assets | Monkey-patched locally; library needs `min_assets` parameter | **Open** |
| 2 | vol_parity weight scheme returns all zeros | All SR=0, ret=0 | Single-asset volatility std() returns NaN; `1.0 / vol` becomes `inf` which gets zeroed out | Fix: handle single-std case in weight computation | **Open** |
| 3 | No REST API for factor-level backtesting | No HTTP endpoint | Factor backtest only exists as Python library (`factor_backtest.py`) | - | **Not a bug** |
| 4 | Agent factor_backtest_tool uses synthetic data | Not real market data | Tool generates random-walk prices, not real OHLCV | - | **Design limitation** |
| 5 | equal and rank produce identical results | Same metrics | With 4 tickers and quantile=0.25, top 1 gets weight 1.0 in both schemes | - | **Not a bug** |
| 6 | Some factors require `vwap` column | `KeyError: 'vwap'` | alpha101_005 and alpha101_050 need VWAP which isn't in basic OHLCV | Compute VWAP from OHLCV or skip in test | **Workaround** |
| 7 | compare_factors() also uses hardcoded min_assets=10 | - | Same issue as Bug #1 — calls backtest_factor() internally | - | **Open** |
| 8 | Look-ahead bias in forward returns | Unrealistic returns (1622%) | Forward return uses same panel data without proper lag/alignment | Should use shifted returns with future data excluded | **Design limitation** |

## Bug Details

### Bug 1: Hardcoded min_assets=10
- **File**: `vinu_features/compute/factor_backtest.py:144`
- **Code**: `if len(f_valid) < 10: # append 0.0, continue`
- **Impact**: Any backtest with <10 assets produces all zeros. Blocks small universes (e.g., 4 tickers). Sector/industry-specific backtests are impossible.
- **Suggested fix**: Add `min_assets: int = 10` parameter to `backtest_factor()` with default 10 for backward compatibility.

### Bug 2: vol_parity fails with small N
- **File**: `vinu_features/compute/factor_backtest.py:183-191`
- **Root Cause**: `r_valid[long_idx].std()` on a single-element Series returns NaN (pandas behavior). Then `1.0 / NaN` → inf, which gets zeroed out.
- **Impact**: vol_parity scheme always produces zero portfolio returns for small universes.
- **Suggested fix**: Check `len(long_idx) >= 2` before computing std, fall back to equal weight if < 2.
