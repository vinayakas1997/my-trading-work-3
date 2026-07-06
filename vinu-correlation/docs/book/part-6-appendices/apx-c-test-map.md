# Appendix C — Test file → module map

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |

| Test file | Module tested | Coverage |
|-----------|---------------|----------|
| `tests/test_impact.py` | `engine/impact.py` | Impact classification, ticker parsing, thread aggregation |
| `tests/test_correlation.py` | `engine/correlation.py` | Resampling, correlation, lag analysis |
| `tests/test_granger.py` | `engine/granger.py` | Granger causality, edge cases |
| `tests/test_event_study.py` | `engine/event_study.py` | Abnormal return, CAR, significance |
| `tests/test_drawdown.py` | `engine/drawdown.py` | Peak detection, attribution |
| `tests/test_baseline.py` | `engine/baseline.py` | Baseline calculation, deviation |
| `tests/test_market_hours.py` | `engine/market_hours.py` | Session classification, window clamping |
| `tests/test_api.py` | `api.py`, `server/` | HTTP endpoints, integration |
| `tests/test_cache.py` | `cache.py` | Cache get/set/invalidate |
| `tests/test_incremental.py` | `storage/backend.py` | Append, dedup, range queries |
