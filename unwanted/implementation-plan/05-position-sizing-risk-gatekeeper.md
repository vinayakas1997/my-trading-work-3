---
name: position-sizing-risk-gatekeeper
closes: shortcoming #7 in ../01-vinu-components-shortcomings.md
ports: fractional Kelly + ATR sizing, per ../02-reference-repos-core-logic.md § "Position sizing for risk_gatekeeper"
status: complete — see 05-position-sizing-risk-gatekeeper-status.md
---

# Task: add a real position-sizing formula to `risk_gatekeeper`

## Goal

`risk_gatekeeper` currently checks portfolio *fit* (correlation, sizing vs. account) but has no formula
deciding *how much* to size an approved candidate. Add one.

## Why

Confirmed gap by direct comparison against the two reference repos — this is a real capability hole, not
a nice-to-have. See `02-reference-repos-core-logic.md` for the full tradeoff analysis between Kelly,
fixed-fractional, ATR-scaled, risk-parity, and optimal-f/CPPI sizing methods. Recommendation there:
fractional Kelly (25-50%), ATR-normalized, sized off the sweep's own PASS-verdict confidence — but that's
a judgment call, not a mandate; fixed-fractional alone is the safer starting point if Kelly isn't trusted
yet.

## Current state (verified 2026-08-17 — re-check before building)

- `risk_gatekeeper` checks the already-approved candidate against the real current portfolio — position
  sizing *vs. account size* (i.e., does this fit within exposure limits) and correlation to what's
  already open, via `get_portfolio` (a real, pre-existing tool). It does **not** currently compute a
  recommended position size from the strategy's own backtested edge — confirm this is still true by
  reading the actual `risk_gatekeeper` team code before starting (path not fully traced in the earlier
  audit — locate it under `vinu-agent`'s teams/hooks structure, likely near `risk_gatekeeper_hook.py`).
- Reference implementation to port from: `jarvis-trading-bot/risk_manager.py` (path:
  `/home/somic_cps/Vina/my-trading-work-3/personal-important/other-reference-repos/jarvis-trading-bot/
  risk_manager.py`) — has real Kelly-criterion sizing and ATR-based dynamic sizing functions. Port the
  math, not the surrounding Telegram/broker app.
- Complementary reference: `Jarvis/core/risk_manager.py` implements fixed-fractional (the "1-2% rule")
  sizing — useful as the simpler fallback/comparison case, or as the actual chosen method if fractional
  Kelly is judged too aggressive to trust yet.

## Steps

1. Read the actual current `risk_gatekeeper` implementation in `vinu-agent` end to end — confirm exactly
   what inputs it already has available (win-rate/Sharpe from the sweep's ranked table, account equity
   from `get_portfolio`, ATR or volatility data availability) before designing the sizing function's
   signature.
2. Read `jarvis-trading-bot/risk_manager.py`'s Kelly and ATR functions in full to understand their exact
   math and required inputs.
3. Implement a new sizing function (e.g. `compute_position_size(win_rate, payoff_ratio, account_equity,
   atr, kelly_fraction=0.25, ...)` — exact signature depends on what step 1 finds available) as a plain,
   testable function — not an LLM call. This is deterministic math, same category as the sweep engine and
   Live+Shadow bookkeeping elsewhere in this codebase.
4. Wire it into `risk_gatekeeper`'s verdict flow so `APPROVED` candidates carry a computed `approved_size`
   (the design doc / Phase 2 plan already reference an `approved_size` field on the artifact model —
   confirm this field exists in `vinu-research/vinu_research/models.py` and reuse it rather than adding a
   new one).
5. Follow the project's traceability discipline: every sizing decision should record which inputs
   produced it (win-rate, payoff ratio, ATR, fraction used) — not just the final number — consistent with
   how every other gate in this pipeline reports a specific, stored reason.
6. Make the Kelly fraction (and whether Kelly or fixed-fractional is used at all) a configurable
   parameter, not hardcoded — this is explicitly called out in the design doc's own "Open questions" as
   undecided ("`capital_allocator`'s allocation math is still provisional... Kelly/risk-parity/other not
   decided").

## Acceptance criteria

- A unit test suite for the new sizing function covering: normal case, zero/negative edge (win-rate ≤ 0
  or payoff ratio ≤ 0 should never produce a positive Kelly size), and a fixed-fractional comparison case.
- `risk_gatekeeper`'s `APPROVED` verdict path populates a real computed size (not a placeholder/default),
  traceable to the specific inputs used.
- Existing `risk_gatekeeper` tests (fit/correlation checks) still pass unmodified — this is an addition,
  not a replacement of the existing portfolio-fit logic.

## Dependencies

None, but pairs naturally with task 06 (walk-forward) since both feed into what `risk_gatekeeper`
receives as "how much edge do we actually believe this has."
