# Task 3: Enhanced Exit Checklist

**Status:** DONE

## Purpose

Expand the exit checklist from 6 conditions to 8, adding:
- **Condition 7: Adverse news catalyst** — scans news articles for negative/bearish sentiment; renders EXIT if found, MONITOR if positive
- **Condition 8: News/price causality divergence** — checks the `news_price_causality` angle for divergence signals

## Approach

- Updated `_render_exit_checklist()` signature to accept `news` parameter
- News sentiment scanning: checks first 3 articles for string sentiment ("negative"/"bearish") or numeric sentiment (< -0.3)
- `_render_plan` passes news data through to exit checklist

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/tools/trade_plan_tool.py` | 1-548 | Modified — _render_exit_checklist extended to 8 conditions with news-based exits |

## Verification

- [x] 8 exit conditions rendered
- [x] Adverse news with negative sentiment triggers EXIT
- [x] Adverse news with numeric sentiment < -0.3 triggers EXIT
- [x] Positive news shows MONITOR
- [x] News_price_causality divergence renders REDUCE when data exists
