# Task 2: Regime Context + Drawdown-by-Regime

**Status:** DONE

## Purpose

Add two new supporting sections to the trade plan:
- **Market Regime** — displays the current regime (bull/bear/crisis), volatility level, correlation, and any extra fields from the `regime_analysis` angle
- **Drawdown by Regime** — shows recent drawdown periods with percentage, duration, and recovery status

## Approach

- `_render_regime_context()` — iterates `regime_analysis` angle, displays regime name, volatility, correlation, and any extra fields dynamically
- `_render_drawdown_by_regime()` — iterates `drawdown_deep_dive` angle (last 5 entries), formats as a table with drawdown %, duration, and recovery
- Both render as subsections under "A. Market Context"

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/tools/trade_plan_tool.py` | 1-548 | Modified — added _render_regime_context, _render_drawdown_by_regime; both called from _render_plan |

## Verification

- [x] Regime context renders regime name, volatility, correlation
- [x] Extra dynamic fields from regime_analysis are included
- [x] Drawdown table renders with %, duration, recovery
- [x] Empty angles produce graceful fallback messages
