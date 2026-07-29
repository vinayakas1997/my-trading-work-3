# Vision: Live Risk, Personality Memory & Execution — Fitted to the 3-Environment Architecture

## Relationship to the existing architecture

This folder was originally drafted against `project-progress-vision/agentic-implementation`'s
13-step roadmap. It has been **re-fitted** to the actual governing architecture:
`my-learning/new-direction-for-the-project.md`'s three isolated environments —

```
Initial-Analysis  ──feeds──>  Research-Simulations  ──approves──>  Live-Trading
  (deterministic)               (LLM-driven)                        (production)
```

— with data flowing downhill only, and execution logs flowing back uphill to Initial-Analysis
for PnL attribution. That document's non-negotiable rule governs every phase below:

> Any LLM or non-deterministic component lives exclusively in Research-Simulations.
> Initial-Analysis and Live-Trading are entirely deterministic — same inputs always produce
> same outputs.

**Clarification this revision corrects:** "zero LLM calls in Live-Trading" does not mean the
LLM is uninvolved in risk, sizing, or in-trade behavior. It means the LLM does **complete
preparation in advance** — the risk parameters, the position size, and the full set of
"how to play during the trade" contingency rules (when to trim, when to hedge, what invalidates
the trade, what to do if it moves against you) — all decided and written down as part of
Research-Simulations' approval step, before the trade starts. Live-Trading then executes that
fully-specified, frozen plan deterministically. No live judgment call is missing — it was
already made, upstream, with time to be checked.

## What doesn't exist yet, in this architecture's own terms

`vinu-live` is named in the architecture doc as `NOT STARTED`, with planned scope already
listing: broker integration, order execution engine, **position sizing and portfolio
allocation**, **real-time risk limits and circuit breakers**, and an execution log that feeds
back to Initial-Analysis for PnL attribution. This vision is the detailed build-out of exactly
that scope, plus the two upstream pieces it depends on that aren't fully built either:

1. **Deterministic risk math** (volatility, VaR, greeks, expected move, position-sizing
   formulas, and — the amendment from this vision's own review — conditional/clustered
   volatility and dynamic cross-symbol covariance) doesn't exist as a shared, reusable
   computation yet.
2. **Personality / after-shock behavioral memory** (gap-fill rate, vol-clustering persistence,
   which symbols shock together) doesn't exist as data anywhere — Initial-Analysis's 19 angles
   cover regime, drawdown, and event-study analysis, but nothing yet characterizes
   *post-shock behavior* as a queryable, confidence-scored fact per symbol.
3. **A complete, frozen, per-strategy trade plan** — sizing rules, risk bands, and in-trade
   contingency rules, authored once at approval time and never revisited live — doesn't exist
   yet either; `TradePlanTool` renders checklists today but isn't yet the binding, exhaustive
   contract Live-Trading would execute against.

## Where each piece actually belongs

Re-homed against the real package boundaries, not invented ones:

| Component | Lives in | Why here, not elsewhere |
|---|---|---|
| Risk-math formulas (vol, VaR, greeks, expected move, sizing, clustering) | `vinu-tools` (`compute/formulas`, alongside the existing `bench`/`ml`/`factors` categories) | It's a shared, deterministic computation library already structured for exactly this — both Initial-Analysis angles and Live-Trading's runtime checks need the same formulas; a shared library prevents two independently-drifting implementations, the same duplication problem `02-storage-memory` flagged for `SQLiteBackend`. |
| Personality / shock-clustering stats | New angle folders in `vinu-initial-analysis` | Deterministic, per-symbol, computed the same way `regime_analysis`/`drawdown_deep_dive`/`event_study_methodology` already are — not a new "memory layer" package (a concept from a different, since-superseded planning doc that this architecture doesn't reference). |
| Forecast generation + full trade-plan authoring (sizing rules, risk bands, in-trade contingency rules) | `vinu-research`, extending the existing refine-and-approve loop and `TradePlanTool` | This is where all non-deterministic judgment must live, per the architecture's own rule. Authored once, gated the same way a strategy is gated, then frozen into an artifact the same way `research_runs`/`Artifact` already persists approved `strategy_code` today. |
| Live position/book ledger, circuit breaker, execution engine | `vinu-live` (new package, matches the architecture's own naming) | Live-only, stateful, deterministic-at-runtime — exactly the "production execution" role already scoped for it. |
| Feedback: execution logs → behavioral/decay updates | Existing `pnl_attribution` angle (Initial-Analysis) and `decay_monitoring`/decay-scan (Research-Simulations), both already partially built | Reuses the downhill/uphill pipe the architecture already defines, instead of inventing a parallel write-back path. |

## Roadmap at a glance

See [01-plan-overview.md](01-plan-overview.md) for the full phased breakdown. In short:

| Phase | Delivers | Environment |
|---|---|---|
| 1 | Shared risk-math library: vol/VaR/greeks/expected-move/sizing, with conditional (GARCH/EGARCH) volatility and dynamic clustered covariance | `vinu-tools` |
| 2 | Personality / shock-clustering angles (gap-fill rate, vol persistence, shock-cluster membership) | `vinu-initial-analysis` |
| 3 | Live position/book ledger | `vinu-live` |
| 4 | Forecast skill + full trade-plan authoring (sizing, risk bands, in-trade contingency rules), gated and frozen at approval | `vinu-research` |
| 5 | Circuit breaker / kill switch, clustering-aware | `vinu-live` |
| 6 | Execution engine + live orchestrator — executes frozen Phase 4 plans against live data, zero runtime LLM calls | `vinu-live` |
| 7 | Feedback-loop closure: execution logs update Initial-Analysis's angles and feed the next Research-Simulations cycle | `vinu-initial-analysis` + `vinu-research` |

None of these phases are approved to start. They are documented so the next agent has the full
picture — including the two corrections this revision makes (package boundaries, and
upfront-preparation vs. live-decision framing) — before any code is written.
