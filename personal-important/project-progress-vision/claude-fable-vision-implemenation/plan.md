# Build Order — Live Risk, Personality Memory & Execution

This is the execution-tracking build order for the vision documented in full in
[`../claude-fable-vision/`](../claude-fable-vision/) — see
[`00-vision-summary.md`](../claude-fable-vision/00-vision-summary.md) for the "why" and
[`01-plan-overview.md`](../claude-fable-vision/01-plan-overview.md) for the source phase table
this mirrors. Each row below has a matching `phase-NN-*.md` design doc there; read it before
starting that phase's folder here.

The plan targets the one environment the governing architecture doc
(`my-learning/new-direction-for-the-project.md`) marks `NOT STARTED` — `vinu-live` — plus the
upstream deterministic risk-math (`vinu-tools`) and research-time trade-plan-authoring
(`vinu-research`) work it depends on. It does **not** modify `vinu-initial-analysis`'s existing
19 angles or `vinu-research`'s existing refine-and-approve loop — it extends both.

---

## Build Sequence

| Phase | Delivers | Package | Depends On | Source Doc |
|-------|----------|---------|------------|-------------|
| 1 | Risk-math formulas: realized + conditional (GARCH/EGARCH) volatility, VaR, greeks, expected move, position-sizing math, and dynamic shrinkage-estimated (Ledoit-Wolf) covariance across a symbol set. Pure computation, importable by every environment. | `vinu-tools` (`compute/risk`, new category alongside existing `formulas`/`bench`/`ml`/`factors`) | — | `phase-01-shared-risk-math.md` |
| 2 | Personality / shock-clustering angles: shock-tagging job joining `vinu-stock-price` + news events, producing `gap_fill_rate`, `vol_persistence` (from Phase 1's GARCH fit), and `shock_cluster_membership` (from Phase 1's dynamic covariance sampled at shock dates) — each with a sample size / confidence interval. | `vinu-initial-analysis` (new angle folders, following the existing self-contained-angle pattern) | Phase 1 | `phase-02-personality-shock-angles.md` |
| 3 | Live position/book ledger: open positions, size, average entry, realized/unrealized PnL, attached stops/targets — the only stateful "what do we hold right now" source of truth. | `vinu-live` (new package) | — | `phase-03-live-book-ledger.md` |
| 4 | **Hinge phase.** Forecast skill (direction/magnitude, gated by a calibration test vs. coin-flip/vol-implied null, same gating pattern as `loop.py`'s Monte Carlo/holdout checks) + full trade-plan authoring extending `TradePlanTool`: position size, risk bands (Phase 1 formulas + Phase 2 personality context), and explicit in-trade contingency rules. Frozen into a versioned artifact via the same approve→artifact bridge that persists `strategy_code` today. | `vinu-research` | Phase 1, Phase 2 | `phase-04-forecast-and-tradeplan-authoring.md` |
| 5 | Circuit breaker / kill switch: max-daily-loss, max-aggregate-VaR, max-greeks-exposure hard limits computed from Phase 1's clustered/dynamic covariance across Phase 3's live book. Deterministic, not LLM-adjustable, checked immediately before every order. Kept as a separate module from Phase 1 so its thresholds require a deliberate, reviewed change to touch. | `vinu-live` | Phase 1, Phase 3 | `phase-05-circuit-breaker.md` |
| 6 | Execution engine + live orchestrator: scheduled/event-driven loop reading a Phase 4 frozen trade-plan artifact, checking current market data against its pre-written conditions, checking Phase 5's breaker last, then placing/managing the order via a broker API. **Zero LLM calls at runtime.** | `vinu-live` | Phase 3, Phase 4, Phase 5 | `phase-06-execution-orchestrator.md` |
| 7 | Feedback-loop closure: Phase 6 execution logs flow into Initial-Analysis's existing `pnl_attribution` angle (dormant until now) and into Research-Simulations' existing `decay_monitoring`/decay-scan — updating Phase 2's confidence intervals and Phase 4's calibration tracking, feeding the next research cycle rather than a live re-decision. | `vinu-initial-analysis` + `vinu-research` | Phase 2, Phase 4, Phase 6 | `phase-07-feedback-loop-closure.md` |

---

## Why Phase 4 Is the Hinge

Phases 1, 3, and 5 are pure math or pure state; Phases 6 and 7 are pure execution/write-back.
Phase 4 is the *only* place judgment happens, and it must happen entirely before Phase 6 ever
runs — never during. "Zero LLM calls at runtime" (Phase 6) only holds up if Phase 4's output is
thorough enough — size, risk bands, and every in-trade contingency rule anticipated — that
Phase 6 never needs to ask the LLM anything new mid-trade. See
[`../claude-fable-vision/01-plan-overview.md`](../claude-fable-vision/01-plan-overview.md) for
the full argument.

**Warning for whoever implements Phase 4:** a thin output — direction and size only, no
contingency rules — will satisfy every mechanical checklist item in `AGENTS.md`, including Rule
10's "no runtime LLM call outside `vinu-research`," while silently reintroducing the exact
failure mode this whole plan exists to prevent: Phase 6 hitting a live scenario Phase 4 never
wrote a rule for, and having nothing to do but improvise or halt blind. Passing Rule 10 is not
the same as this phase having done its job. Do not mark Phase 4 `completed` on tests-pass alone
— the source doc's "Completeness test" (every contingency rule mechanically evaluable, no
free-text instruction requiring interpretation) is the actual bar.

---

## The Architecture's Non-Negotiable Rule

Per `my-learning/new-direction-for-the-project.md`: any LLM or non-deterministic component lives
**exclusively** in Research-Simulations (`vinu-research`, i.e. Phase 4 and the research-side half
of Phase 7). `vinu-initial-analysis` (Phases 2, and the angle-side half of Phase 7) and
`vinu-live` (Phases 3, 5, 6) must be entirely deterministic — same inputs always produce the same
outputs. Every phase's `00-implementation.md` must confirm this holds before being marked
`completed`.

---

## Parallelization Opportunities

- **Phases 1 + 3** can run in parallel — shared risk math and the live book ledger have no dependency on each other
- **Phase 2** can start as soon as Phase 1 lands, independent of Phase 3
- **Phase 5** only needs Phases 1 + 3, so the circuit breaker and live book visibility can exist and be tested well before Phase 4's forecast/trade-plan authoring is trusted enough to approve anything

---

## Open Design Question (Phase 4)

Whether the frozen Phase 4 trade-plan artifact is stored as a new table alongside
`Artifact`/`BenchEntry` in `vinu-research`'s existing storage, or as a new document type inside
`vinu-strategy`, is left open in the source doc — resolve it in Phase 4's `00-implementation.md`
before writing task files, and record the decision there (also update this row once decided).

---

## Files Touched, by Package (Projected)

| Package | Phases | Notes |
|---|---|---|
| `vinu-tools` | 1 | New `compute/risk` category; consumed read-only by every other phase |
| `vinu-initial-analysis` | 2, 7 | New angle folders; existing `pnl_attribution` angle goes from dormant to live |
| `vinu-research` | 4, 7 | Extends existing `loop.py` gating pattern and `TradePlanTool`; existing `decay_monitoring`/decay-scan gains a real feed |
| `vinu-strategy` | 4 (possible) | Candidate home for the frozen, versioned trade-plan artifact — see Open Design Question above |
| `vinu-live` (new) | 3, 5, 6 | The only new package; matches the name and scope already planned in the architecture doc |
| `vinu-agent` | 6, 7 | `TradePlanTool`/conversational tools become consumers of Phase 4's frozen plans and Phase 7's feedback, not the authoring surface itself |
