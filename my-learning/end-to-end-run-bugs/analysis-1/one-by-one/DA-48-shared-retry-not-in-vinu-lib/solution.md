# DA-48 🟠 Shared retry utility not in vinu-lib

**Component:** `vinu-lib`
**Files Changed:** `vinu-lib/retry.py`, `vinu-stock-price/providers/alpaca.py`, `vinu-stock-price/providers/yahoo.py`, `vinu-stock-price/providers/polygon.py`, `vinu-stock-price/providers/tushare.py`, `vinu-stock-price/tests/test_provider_retry.py`, `vinu-stock-price/providers/retry.py`

## Problem

`vinu-stock-price/vinu_stock/providers/retry.py` contains a well-tested retry utility (`retry_on_transient` decorator, `http_get_with_retry`, `http_post_with_retry`) but it lives inside vinu-stock-price. Other components cannot import it without reaching across packages, creating an unnecessary barrier. Future retry fixes (DA-50 through DA-55) need this in a shared location.

## Root Cause

The code evolved organically — the retry helper was built for stock-price providers and stayed in that package. vinu-lib existed but wasn't used as the staging ground for cross-cutting infrastructure.

## Solution

Moved `retry.py` from vinu-stock-price to vinu-lib (with updated docstring). vinu-lib already depends on `requests>=2.31` and vinu-stock-price already imports from vinu-lib at runtime — no circular dependency risk, no new dep needed.

### Files changed

| File | Change | Lines |
|------|--------|-------|
| `vinu-lib/retry.py` | **Created** — copy of source with updated docstring | +95 |
| `vinu-stock-price/providers/alpaca.py:13` | `vinu_stock.providers.retry` → `vinu_lib.retry` | 1 |
| `vinu-stock-price/providers/yahoo.py:12` | `vinu_stock.providers.retry` → `vinu_lib.retry` | 1 |
| `vinu-stock-price/providers/polygon.py:13` | `vinu_stock.providers.retry` → `vinu_lib.retry` | 1 |
| `vinu-stock-price/providers/tushare.py:16` | `vinu_stock.providers.retry` → `vinu_lib.retry` | 1 |
| `vinu-stock-price/tests/test_provider_retry.py:6` | `vinu_stock.providers.retry` → `vinu_lib.retry` | 1 |
| `vinu-stock-price/providers/retry.py` | Replaced with 4-line backward-compat re-export shim | −93 |

The old `vinu-stock-price/providers/retry.py` is kept as a backward-compatibility shim that re-exports all 4 public symbols from `vinu_lib.retry`. Any external code still importing from the old path continues to work without changes.

### Verification

1. `python -c "import ast; ast.parse(open('vinu-lib/retry.py').read()); print('syntax OK')"` — passes
2. `from vinu_lib.retry import http_get_with_retry, http_post_with_retry, retry_on_transient, TransientProviderError` — all 4 symbols resolve
3. `from vinu_stock.providers.retry import http_get_with_retry` — backward-compat shim works
4. `pytest vinu-stock-price/tests/test_provider_retry.py -v` — 1 passed
