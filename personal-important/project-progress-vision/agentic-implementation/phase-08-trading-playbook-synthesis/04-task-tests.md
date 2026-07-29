# Task 4: Tests for Enhanced Playbook Features

**Status:** DONE

## Purpose

Add comprehensive test coverage for all new and enhanced methods in the TradePlanTool.

## Approach

- 33 new tests in `test_trade_plan_playbook.py` covering:
  - `_extract_trend_bias` — 5 tests (bullish, bearish from stage, bearish from direction, neutral, no data)
  - `_render_regime_context` — 3 tests (with data, empty, extra fields)
  - `_render_drawdown_by_regime` — 2 tests (renders table, skips when empty)
  - `_render_news_sensitivity` — 3 tests (renders table, unavailable, None)
  - `_render_time_of_day_guidance` — 2 tests (renders sessions, ordering)
  - `_render_long_entry_checklist` — 2 tests (6 conditions, trend PENDING)
  - `_render_short_entry_checklist` — 1 test (renders short conditions)
  - `_fetch_news` — 4 tests (available, 404, empty, connection error)
  - `_render_exit_checklist` — 4 tests (8 conditions, negative string sentiment, negative numeric, positive)
  - `_fetch_active_strategies` — 2 tests (matching strategies, 404)
  - `_render_active_strategies` — 2 tests (renders table, skips empty)
  - `_render_tranches` — 3 tests (with bias, short direction, trailing stop)

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/tests/test_trade_plan_playbook.py` | 1-313 | Created — 33 tests for all enhanced playbook features |

## Verification

- [x] All 33 new tests pass
- [x] All 136 existing tests still pass (no regressions)
- [x] httpx.MockTransport used for HTTP-dependent tests
- [x] Edge cases covered (empty data, errors, unavailable services)
