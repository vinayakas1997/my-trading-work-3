# Bugs Found: Angle 17 — Fundamentals

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Corporate actions API endpoint deprecated/removed | `HTTP 404` | Alpaca moved from `v1beta1/corporate-actions/announcements` to `v1/corporate-actions`. Parameters also changed: `symbol` → `symbols`, `types: 'dividend'` → nested under `cash_dividends` key | Changed URL and params. Response structure is `corporate_actions.cash_dividends[]` | `angle17_fundamentals.py:41` | Medium | Fixed |

## Notes
- Alpaca API only provides corporate actions (dividends, splits), not fundamental financials (PE, ROE, etc.)
- yfinance is used for full fundamentals — the same library vinu-stock-price uses internally for its YFinanceProvider
- Some fields (e.g., PEG ratio, EV/EBITDA) are not consistently available across all tickers

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
