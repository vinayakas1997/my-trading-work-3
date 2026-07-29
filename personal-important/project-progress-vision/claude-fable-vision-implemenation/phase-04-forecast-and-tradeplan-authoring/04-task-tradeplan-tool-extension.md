# Task 4: TradePlanTool Extension

**Status:** DONE

## Purpose

Extend TradePlanTool to surface the Phase 4 frozen `TradePlan` (forecast + risk bands +
contingency rules, authored and frozen server-side in `vinu-research`) alongside its existing
human-readable markdown + ad-hoc dict-based structured plan.

## Approach — revised from the original plan

The original approach text (`_build_trade_plan()` builds the structured object *inside*
`TradePlanTool`) would have put forecast generation — an LLM call — inside `vinu-agent`,
violating Rule 10 (LLM lives exclusively in `vinu-research`). Instead: `vinu-research` authors
and freezes the plan server-side (`trade_plan_authoring.author_trade_plan` +
`freeze_trade_plan`, exposed via `POST /research/trade-plan/{symbol}`), and `TradePlanTool`
only *fetches* the already-frozen artifact — the same read-only-consumer pattern it already
uses for `_fetch_active_strategies`. No LLM call was added to `vinu-agent`.

- `_fetch_frozen_trade_plan()`: POSTs to the new endpoint, swallows failures into
  `{"status": "unavailable"|"error"}` like every other fetch helper in this file.
- `_render_frozen_plan_block()`: renders the artifact as a second, separately-marked JSON
  block (`<!-- frozen_trade_plan -->`) appended after the existing
  `<!-- structured_plan -->` block.
- `_build_structured_plan()` / `_render_plan_json_block()` (the pre-existing ad-hoc
  dict-based plan) were **not modified** — they back three already-passing test files
  (`test_trade_plan_liquidity.py`, `test_trade_plan_playbook.py`, `test_trade_plan_validation.py`)
  and still pass unchanged.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_agent/tools/trade_plan_tool.py` | `_execute_async`, new `_fetch_frozen_trade_plan`/`_render_frozen_plan_block` | Added frozen-trade-plan consumer, appended as an additional output block |

## Verification

- [x] Tests pass (`tests/test_trade_plan_frozen.py`, 5 tests; existing 3 trade-plan test files unchanged and still pass — 46 total)
- [x] No runtime LLM call introduced in `vinu-agent`
