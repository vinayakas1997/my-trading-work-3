# Chapter 14 — Market hours & session awareness

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/engine/market_hours.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch02 |

## 1. Problem

Price impact of news depends on whether markets are open. A news article at 2 PM (regular session) will have a different price reaction than one at 2 AM (closed). The market hours module provides session classification and impact window clamping.

## 2. Sessions (UTC)

| Session | Hours | Name |
|---------|-------|------|
| Pre-market | 8–13 | `pre_market` |
| Regular | 13–20 | `regular` |
| After-hours | 20–24 | `after_hours` |
| Closed | 0–8 | `closed` |

## 3. Impact windows

| Window | Seconds |
|--------|---------|
| 5m | 300 |
| 15m | 900 |
| 30m | 1800 |
| 1h | 3600 |
| 1d | 86400 |

## 4. Window clamping

`impact_window_within_session()` ensures the impact window does not extend past the session boundary. For example, a 1h impact window on an article at 19:30 (regular session) is clamped to end at 20:00.

## 5. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_market_hours.py` | Session classification, window clamping |
