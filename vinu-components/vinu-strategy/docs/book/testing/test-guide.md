# Test Guide

## Overview

This guide covers testing vinu-strategy including unit tests, integration tests, and strategy validation.

## Test Suite

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_risk.py

# Run specific test method
pytest tests/test_risk.py::TestRisk::test_normalize

# Run with coverage
pytest --cov=vinu_strategy --cov-report=html
```

### Test Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| `engine/risk.py` | 100% | Passing |
| `engine/expression.py` | 100% | Passing |
| `engine/allocation.py` | 100% | Passing |
| `engine/selection.py` | 100% | Passing |
| `engine/rules_engine.py` | 100% | Passing |
| `service.py` | 95% | Passing |
| `api.py` | 90% | Passing |

**Total**: 56 tests, 0 failures

## Unit Tests

### Risk Tests

**File**: `tests/test_risk.py`

**Tests**:
- `test_normalize` - Basic normalization
- `test_normalize_capped` - Cap at max weight
- `test_normalize_empty` - Empty weights
- `test_none_passthrough` - No normalization
- `test_normalize_below_cap` - Below cap no scaling
- `test_capped_above_cash_floor` - Scale when above cash floor
- `test_unknown_fallback` - Unknown method fallback
- `test_normalize_with_shorts` - Handle short positions
- `test_normalize_with_shorts_capped` - Cap shorts
- `test_normalize_with_shorts_scaled` - Scale with shorts
- `test_normalize_with_shorts_allow_short_false` - Long-only mode
- `test_normalize_with_shorts_allow_short_false_all_short` - All shorts long-only
- `test_normalize_with_shorts_max_short_weight` - Custom short weight

**Example**:
```python
def test_normalize_with_shorts(self):
    weights = {"AAPL": 0.167, "MSFT": -0.167}
    result = run_risk("normalize", weights, {
        "max_weight": 0.25,
        "cash_floor": 0.10
    })
    assert abs(result["AAPL"] - 0.167)