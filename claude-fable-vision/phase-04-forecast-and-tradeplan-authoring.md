# Phase 4 — Forecast Skill + Full Trade-Plan Authoring (the hinge phase)

Status: **not started** · Depends on: Phase 1 (risk math), Phase 2 (personality angles) · Blocks: Phase 5, Phase 6, Phase 7

## What it is

This is the only phase in the whole plan where judgment happens, and it must happen entirely
inside Research-Simulations, entirely before a trade ever starts — never live. It has two parts
that ship together, never one without the other:

1. **Forecast skill** — direction + magnitude, built from Phase 2's personality features
   (`gap_fill_rate`, `vol_persistence`, `shock_cluster_membership`) and Phase 1's risk state,
   using the same LLM-assisted generate/backtest/refine loop `loop.py` already runs for
   strategies (`_quant_coder`/`_risk_critic` pattern). Gated by a **calibration test** —
   directional accuracy vs. a coin-flip null, magnitude error vs. a volatility-implied null,
   scored with a proper scoring rule (Brier score or CRPS) — tracked continuously, the same way
   `decay_monitoring` already tracks strategy health. A forecast that stops passing calibration
   is cut off from Phase 6 automatically, the same way a strategy failing the Monte Carlo/holdout
   checks is blocked from promotion automatically.

2. **Full trade-plan authoring** — extending `TradePlanTool` from "renders a checklist" to
   "produces the complete, binding contract Live-Trading will execute against." This is the
   correction to the earlier "zero LLM calls" framing: the LLM is not absent from live risk
   decisions, it makes **all of them in advance**, exhaustively, as part of this plan:
   - **Position size and risk bands** — using Phase 1's VaR/greeks/expected-move numbers as
     inputs, not guessed.
   - **In-trade contingency rules** — explicit, evaluable conditions: "if drawdown exceeds X%,
     trim by Y%," "if realized volatility diverges from Phase 1's estimate at entry by Z, tighten
     the stop," "if a shock hits a symbol in this one's `shock_cluster_membership` group, reduce
     exposure by W%." These are not vague guidance for a human to interpret — they must be
     concrete enough for Phase 6's execution engine to evaluate mechanically against live data,
     with no ambiguity requiring a fresh judgment call.
   - **Invalidation conditions** — the explicit set of facts that mean the original thesis is
     wrong and the position should be closed, not adjusted.

The completed plan is **frozen into a versioned artifact** the same way `research_runs`/
`Artifact` already persists the winning candidate's `strategy_code` on approval today — once
frozen, it does not change without going back through this phase again.

## Impact

**Before this phase:** No component forecasts direction/magnitude at all — the existing pipeline
validates whether a strategy *already* worked historically, it doesn't predict tomorrow. And
`TradePlanTool` produces a document for a human to read, not a machine-evaluable contract.

**After this phase:** Every approved strategy carries a complete, frozen, contingency-covered
plan — sized, risk-banded, and specified for every anticipated in-trade scenario — with a forecast
gated by a continuously-tracked calibration test.

**What still won't work after this phase alone:** A frozen plan with nothing executing it is
inert. Phase 6 is what evaluates it against live data and acts.

## Where changes occur

- Forecast skill: new module in `vinu-research`, alongside `loop.py`'s existing judgment calls,
  reusing its LLM-provider configuration (provider-agnostic, local-Ollama-by-default) rather than
  introducing a second LLM integration path.
- Calibration tracking: extends whatever tracking `decay_monitoring`/decay-scan already provides
  for strategy health — do not build a second, parallel calibration system for forecasts.
- `TradePlanTool` (`vinu-agent/vinu_agent/tools/trade_plan_tool.py`) — extended from
  checklist-rendering to structured, machine-evaluable plan output. The rendered checklist a
  human reads and the structured contract Phase 6 executes against should be two views of the
  same underlying plan object, not two separately-maintained things.
- Frozen artifact storage: extends the existing approve→artifact bridge (`research_runs`,
  `Artifact`, `BenchEntry`) or lives in `vinu-strategy` alongside approved strategy YAML — see
  `01-plan-overview.md`'s open design question; whichever, it must be a single, versioned,
  read-only-once-approved record.

## Why we need this — and why thin output here is the actual risk

This phase is where the earlier framing mistake would resurface if under-built: a forecast that
only outputs "up, 2%" with no contingency coverage forces Phase 6 to make live judgment calls
it isn't designed for — which either means it silently reintroduces an LLM at runtime (breaking
the architecture's core rule) or it acts blindly the first time something unanticipated happens
(the actual danger). The fix is not a lighter-weight live decision layer; it's making this
phase's output exhaustive enough that Phase 6 never has to improvise. That's a genuinely harder
authoring job than a simple direction call, and it should be treated as the highest-scrutiny
output in the entire vision — the same way Stage 0's Monte Carlo gate was designed to be
un-bypassable, this phase's completeness should be checked, not assumed.

## How to test it

- Calibration test: run the forecaster over historical data it wasn't tuned on; compare
  directional accuracy against a coin-flip null and magnitude error against a volatility-implied
  null using a proper scoring rule.
- Fail-closed test: when calibration data is missing or the test is failing, confirm any attempt
  to freeze/approve a plan using that forecast is blocked, not silently allowed — mirrors the
  fail-open bug Step 4 of the base roadmap found and fixed in `_check_mc_gate`.
- Completeness test: for a sample of approved plans, confirm every contingency rule is
  mechanically evaluable (a boolean condition over defined inputs) with no free-text instruction
  requiring interpretation.
- Drift test: feed the calibration tracker a sequence of forecasts that start accurate and
  degrade; confirm the gate flips to failing within a bounded number of observations.
- Freeze-immutability test: confirm an approved, frozen plan cannot be mutated in place — a
  revision requires a new version, re-approved through this same phase.
