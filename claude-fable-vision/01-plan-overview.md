# Build Order — Live Risk, Personality Memory & Execution (fitted to the 3-environment architecture)

This plan targets the one environment `my-learning/new-direction-for-the-project.md` marks
`NOT STARTED` (`vinu-live`) plus the upstream deterministic and research-time work it depends on.
It does not modify `vinu-initial-analysis`'s existing 19 angles or `vinu-research`'s existing
refine-and-approve loop — it extends both.

---

## Build Sequence

| Phase | Delivers | Package | Depends On |
|-------|----------|---------|------------|
| 1 | Risk-math formulas: realized + conditional (GARCH/EGARCH) volatility, VaR, greeks, expected move, position-sizing math, and dynamic shrinkage-estimated covariance across a symbol set. Pure computation, importable by every environment. | `vinu-tools` (`compute/` — new `risk` category alongside existing `formulas`/`bench`/`ml`/`factors`) | — |
| 2 | Personality / shock-clustering angles: a shock-tagging job joining `vinu-stock-price` and news events, producing `gap_fill_rate`, `vol_persistence` (derived from Phase 1's GARCH fit), and `shock_cluster_membership` (which symbols shock together, from Phase 1's dynamic covariance sampled at shock dates) — each with a sample size / confidence interval, never a bare point estimate. | `vinu-initial-analysis` (new angle folders, following the existing self-contained-angle pattern) | Phase 1 |
| 3 | Live position/book ledger: open positions, size, average entry, realized/unrealized PnL, attached stops/targets — the only stateful "what do we hold right now" source of truth. | `vinu-live` (new package) | — |
| 4 | Forecast skill + full trade-plan authoring: direction/magnitude forecast, gated by a calibration test (skill vs. a coin-flip/vol-implied null) the same way strategies are gated by the Monte Carlo/holdout checks already in `loop.py`; and — extending `TradePlanTool` — a **complete** upfront plan per approved strategy: position size, risk bands (using Phase 1's formulas + Phase 2's personality context), and explicit in-trade contingency rules ("if drawdown exceeds X, trim by Y," "if realized vol diverges from Phase 1's estimate by Z, tighten stop"). Frozen into a versioned artifact via the same approve→artifact bridge that already persists `strategy_code` in `research_runs`/`Artifact`. | `vinu-research` | Phase 1, Phase 2 |
| 5 | Circuit breaker / kill switch: max-daily-loss, max-aggregate-VaR, max-greeks-exposure hard limits, computed from Phase 1's clustered/dynamic covariance across Phase 3's live book — not a sum of independent per-symbol numbers. Deterministic, not LLM-adjustable, checked immediately before every order. | `vinu-live` | Phase 1, Phase 3 |
| 6 | Execution engine + live orchestrator: a scheduled/event-driven loop that reads a Phase 4 frozen trade-plan artifact, checks current market data against its pre-written conditions, checks Phase 5's breaker last, and places/manages the order via a broker API. **Zero LLM calls at runtime** — every decision was already made in Phase 4; this phase only evaluates pre-written conditions against live data. | `vinu-live` | Phase 3, Phase 4, Phase 5 |
| 7 | Feedback-loop closure: execution logs from Phase 6 flow into Initial-Analysis's existing `pnl_attribution` angle (currently dormant, per the architecture doc, "until Live-Trading") and into Research-Simulations' existing `decay_monitoring`/decay-scan — updating Phase 2's personality confidence intervals with new shock observations and Phase 4's calibration tracking with realized forecast accuracy, feeding the *next* research cycle rather than a live re-decision. | `vinu-initial-analysis` + `vinu-research` | Phase 6, Phase 2, Phase 4 |

---

## Why Phase 4 is the hinge of this whole plan

Every other phase is either pure math (1, 5) or pure state (3) or pure execution (6, 7). Phase 4
is the only place where judgment happens — and it must happen entirely *before* Phase 6 ever
runs, never during. This is the direct fix for the earlier framing mistake: it is not that the
LLM is absent from live trading, it's that the LLM's output — a complete plan covering entry
size, risk bands, and every in-trade contingency the authors could anticipate — is thorough
enough that Phase 6 never needs to ask it anything new. A thin Phase 4 output (just a direction
and a size, no contingency rules) would force Phase 6 to make live judgment calls it isn't built
for; a thorough one is what makes "zero LLM calls at runtime" actually work instead of just
being a rule that gets quietly broken the first time a trade does something unanticipated.

---

## Parallelization Opportunities

- **Phases 1 + 3** can run in parallel — shared risk math and the live book ledger have no
  dependency on each other.
- **Phase 2** can start as soon as Phase 1 lands (it consumes Phase 1's GARCH/covariance
  output), independent of Phase 3.
- **Phase 5** only needs Phases 1 + 3, so the circuit breaker and live book visibility can exist
  and be tested well before Phase 4's forecast/trade-plan authoring is trusted enough to
  approve anything — a desk can have hard limits and book visibility running long before it
  lets Phase 6 place a single order.

---

## Files Touched, by Environment (Projected)

| Package | Phases | Notes |
|---|---|---|
| `vinu-tools` | 1 | New `compute/risk` category; consumed read-only by every other phase |
| `vinu-initial-analysis` | 2, 7 | New angle folders; existing `pnl_attribution` angle goes from dormant to live |
| `vinu-research` | 4, 7 | Extends existing `loop.py` gating pattern and `TradePlanTool`; existing `decay_monitoring`/decay-scan gains a real feed |
| `vinu-strategy` | 4 | Likely home for the frozen, versioned trade-plan artifact — same "approved config" role it already plays for strategy YAML |
| `vinu-live` (new) | 3, 5, 6 | The only new package; matches the name and scope already planned in the architecture doc |
| `vinu-agent` | 6, 7 | `TradePlanTool`/conversational tools become consumers of Phase 4's frozen plans and Phase 7's feedback, not the authoring surface itself |

---

## Open Design Question for the Next Agent

Whether the frozen Phase 4 trade-plan artifact is stored as a new table alongside `Artifact`/
`BenchEntry` in `vinu-research`'s existing storage, or as a new document type inside
`vinu-strategy` (which the architecture doc already calls "the natural 'approved strategy'
representation for Live-Trading") is not decided here on purpose — resolve it the same way the
architecture doc's own open item ("decide Python-code vs strategy-YAML handoff") gets resolved,
since a trade plan and an approved strategy are the same kind of hand-off problem and should
probably share one answer, not two.
