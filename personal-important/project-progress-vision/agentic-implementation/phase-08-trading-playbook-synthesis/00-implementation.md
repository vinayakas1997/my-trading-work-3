# Phase 08: Trading Playbook Synthesis

**Status:** COMPLETED
**Started:** 2026-07-26
**Depends on:** Step 3 (MC validation) — done; Step 6 (comparative critique) — done
**Blocks:** Step 11 (integration testing)

## What It Delivers

Enhanced `TradePlanTool` that produces a richer, context-aware trading playbook:
- **Long/short split** — separate entry conditions for both directions based on trend lifecycle
- **News-sensitivity handling** — recent news headlines + sentiment in entry/exit decisions
- **Time-of-day guidance** — intraday session patterns (pre-market, power hour, closing)
- **Regime context section** — market regime data and drawdown-by-regime analysis
- **Enhanced exit checklist** — news-based triggers, regime-based exits, tighter conditions

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-agent/vinu_agent/tools/trade_plan_tool.py` | vinu-agent | modify (complete rewrite — enhanced with long/short entry, news, regime, time-of-day, 8-condition exit) |
| `vinu-agent/tests/test_trade_plan_playbook.py` | vinu-agent | create (33 tests) |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-enhance-entry.md` | Long/short entry split + news sensitivity + time-of-day zones | DONE |
| 2 | `02-task-regime-drawdown.md` | Regime context section + drawdown-by-regime | DONE |
| 3 | `03-task-exit-checklist.md` | Enhanced exit checklist with news/regime triggers | DONE |
| 4 | `04-task-tests.md` | Tests for enhanced playbook features | DONE |

## Dependencies Met

- [x] Step 3 completed — MC validation p-value available in plan
- [x] Step 6 completed — cross-run reasoning data available
- [x] News API endpoint exists (`/search`) for live news fetch
- [x] All required angles available via initial-analysis API
