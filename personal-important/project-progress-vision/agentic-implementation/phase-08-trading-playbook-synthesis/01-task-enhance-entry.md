# Task 1: Enhance Entry Checklist with Long/Short Split + News Sensitivity + Time-of-Day Zones

**Status:** DONE

## Purpose

Enhance the trade plan entry section from a single generic checklist to a structured playbook with:
- **Long entry conditions** (6 conditions: trend, signal, session, liquidity, drawdown, news/price causality)
- **Short entry conditions** (4 conditions, shown only when trend is bearish/weak)
- **News context table** — recent headlines with sentiment inline
- **Time-of-day guidance** — intraday session zones (pre-market, power hour open, midday, power hour close, after-hours)

## Approach

- `_extract_trend_bias()` — new method that parses `trend_lifecycle` direction/stage to return bullish/bearish/neutral
- `_render_news_sensitivity()` — fetches recent news (via `_fetch_news`) and renders a table with date, headline, sentiment, source
- `_render_long_entry_checklist()` — enhanced version of old `_render_entry_checklist` with 6 conditions including news_price_causality
- `_render_short_entry_checklist()` — new method with short-specific conditions (trend, session bias, liquidity, squeeze risk)
- `_render_time_of_day_guidance()` — new method rendering intraday session table with "← Now" marker for current session
- `_render_plan()` updated to call these methods and conditionally show short checklist
- `_execute_async()` now fetches news in parallel with other data sources

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/tools/trade_plan_tool.py` | 1-548 | Modified — added _extract_trend_bias, _fetch_news, _render_news_sensitivity, _render_long_entry_checklist, _render_short_entry_checklist, _render_time_of_day_guidance; updated _execute_async and _render_plan |

## Verification

- [x] _extract_trend_bias returns bullish/bearish/neutral correctly
- [x] Long entry checklist has 6 conditions with news_price_causality
- [x] Short entry checklist renders only when bias is bearish
- [x] News context table renders headlines with sentiment
- [x] Time-of-day guidance shows session table with current session marker
- [x] _fetch_news handles available/unavailable/empty/error cases
