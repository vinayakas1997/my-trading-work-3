# Task 2: Wire Correlation Gate into Promotion

**Status:** DONE

## Purpose

Integrate the correlation gate into the strategy promotion pipeline so that highly-correlated strategies are created as BENCHING (monitoring-only) instead of ACTIVE.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/config.py` | 114-115 | Added `promotion_correlation_threshold: float = 0.85` and `promotion_correlation_required: bool = False` |
| `vinu-research/vinu_research/config.py` | 216-223 | Added env var loading for both fields |
| `vinu-research/vinu_research/promotion.py` | 4 | Added `CorrelationVerdict` import |
| `vinu-research/vinu_research/promotion.py` | 29 | Added optional `correlation_verdict` parameter to `meets_promotion_bar` |
| `vinu-research/vinu_research/promotion.py` | 58-60 | Appends correlation verdict reasons to bar reasons |
| `vinu-research/vinu_research/service.py` | 12 | Added `check_correlation_gate` import |
| `vinu-research/vinu_research/service.py` | 247-279 | `approve_run`: fetches active strategies, runs correlation gate, sets target status to BENCHING if blocked |
| `vinu-research/vinu_research/service.py` | 281 | `_create_artifact_from_run`: added `status` parameter (default ACTIVE) |

## Verification

- [x] Existing 77 service + loop tests pass
- [x] New test coverage in test_correlation_gate.py passes
