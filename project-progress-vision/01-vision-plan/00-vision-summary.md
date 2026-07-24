# Vision: 4-Stage Strategy-Validation Pipeline

## The problem today

A new strategy proposed for a ticker goes through an ad-hoc process: an LLM agent (or a
human) generates code, calls `run_strategy`/`run_backtest`, reads the metrics, and decides
whether it looks good enough. There is no enforced quality gate, no systematic comparison
against what's been tried before, and no structured hand-off from "this strategy backtests
well" to "here is exactly how to trade it live."

Three concrete gaps were found by architecture investigation:

1. **Monte Carlo validation exists but never runs.** `vinu-simulator/vinu_simulator/engine/validation.py`
   implements a trade-permutation significance test (`monte_carlo_permutation`), a bootstrap
   Sharpe confidence interval (`bootstrap_sharpe_ci`), and a walk-forward consistency check
   (`walk_forward_consistency`). All three are wired behind a `run_validation: bool = False`
   flag on the simulator's `/simulate` and `/simulate/custom` requests. **No caller in the
   codebase ever sets this to `True`** — not the agent's backtest tool, not `vinu-research`'s
   research loop. Confirmed empirically: all 41 real `run_card.json` files on disk lack a
   `validation` key. Even when triggered, the results are written *only* to an on-disk
   `run_card.json`/`run_card.md` file — never into the SQLite meta store, never returned by
   any API route — so the one place that tries to read it back
   (`vinu-agent/vinu_agent/tools/trade_plan_tool.py`'s `_fetch_validation`) always gets `{}`
   and renders "Monte Carlo p-value: N/A".

2. **Refinement exists but has no gate and thin cross-run memory.** `vinu-research`'s
   `StrategyResearchLoop` (`vinu-research/vinu_research/loop.py`) already implements a
   generate → backtest → critique → refine loop with a rule-based + LLM risk critic, stopping
   conditions, and holdout validation. This is most of "Stage 1." But it never invokes the
   Monte Carlo gate, and it only persists the *winning* iteration's code to SQLite — the full
   iteration-by-iteration history (what was tried, why it was rejected) lives only in an
   in-memory list for the duration of one run and is flattened into a markdown report
   afterward, not kept as structured/queryable data.

3. **Nothing compares a strategy against its own history or siblings.** There is no code that
   looks at a strategy about to be promoted and asks "would a different indicator, or a
   strategy tried for this ticker six weeks ago, have done better here?" `comparison.py`'s
   `rank_candidates()` only ranks sibling candidates generated within a single
   generate/refine step of one run — it never looks across runs.

4. **The live-trading playbook is a good partial draft.** `vinu-agent/vinu_agent/tools/trade_plan_tool.py`
   already renders entry checklists, staged profit-taking tranches, and an exit/invalidation
   checklist (including a Monte Carlo p-value line that's always "N/A" per gap #1). It's
   missing drawdown-by-market-regime, an explicit long vs. short split, news-sensitivity /
   consecutive-news handling, and time-of-day/day-of-week timing guidance.

## The proposed pipeline

```
Stage 0: Monte Carlo Gate  →  Stage 1: Refinement  →  Stage 2: Comparative Critique  →  Stage 3: Trading Playbook
   (hard pass/fail)            (iterate until PASS)      (multiple improvement angles)     (live-trading dossier)
```

**Stage 0 — Monte Carlo validation gate.** Before a new strategy proposed for a ticker is
allowed to proceed to refinement at all, it must clear a Monte Carlo significance test: is
the backtest's performance distinguishable from a random reordering/resampling of its own
trades and price path, or could the same Sharpe have come from luck? This is a deterministic,
code-level gate — not something an LLM can be talked out of enforcing.

**Stage 1 — Refinement.** For a strategy that clears the gate, an agent iteratively proposes
refinements (parameter tweaks, added filters/conditions) and re-validates, stopping once it
either reaches an acceptable optimization level (PASS) or exhausts its iteration budget/hits a
stop condition. This reuses `StrategyResearchLoop` almost as-is, with the Stage 0 gate now
enforced on every iteration, not skipped.

**Stage 2 — Comparative critique.** Once a strategy passes Stage 1, a second agent looks across
the *full* history of iterations for this ticker (not just this run) — including prior
promoted/attached strategies — and proposes multiple distinct improvement angles: "this
strategy could refine toward using indicator X instead of Y," "combining this with step Z (used
successfully in a prior run for this ticker) would likely help," and so on. This produces a
*list* of angles with supporting evidence, not a single verdict — the point is to surface
alternatives a human or a later iteration might pursue, not to force one answer.

**Stage 3 — Trading-conditions playbook.** For the strategy (and any surviving angles from
Stage 2), synthesize a concrete live-trading dossier: expected drawdown and under what market
regime it tends to occur, key risk points to watch for live, entry conditions for long
positions and separately for short positions, which categories of news should make you wait
before entering, how to handle clustered/consecutive news events, and timing considerations
(time of day, day of week). This extends the existing `TradePlanTool`.

## Why the stages are ordered this way

Each stage's output is an input to the next: Stage 1 only refines strategies that already
cleared the statistical-significance bar (Stage 0), so refinement time isn't spent polishing
noise. Stage 2 only compares strategies that already reached an acceptable optimization level
(Stage 1's PASS), so the comparison is between genuinely competitive candidates, not
half-baked ones. Stage 3 only writes a live-trading dossier for a strategy that's been
validated, refined, and critiqued — so the playbook reflects a strategy's *actual* tested
behavior (including the regimes/conditions it's fragile in), not just its headline Sharpe.

## Orchestration recommendation

The four stages split cleanly by how much judgment they require:

- **Stage 0 is deterministic and must not be skippable.** It belongs entirely in code, inside
  `vinu-simulator`'s service layer and `vinu-research`'s backtest call path — never left to an
  LLM agent's discretion to remember to invoke.
- **Stages 1–2 are LLM-judgment loops with a strict, non-negotiable sequence** (refine until
  PASS, *then* compare) and hard data dependencies (Stage 2 needs Stage 1's completed iteration
  history). These stay inside `vinu-research`'s existing code-orchestrated pipeline
  (`StrategyResearchLoop.run()`), which already calls LLMs internally for judgment
  (`_quant_coder`, `_risk_critic`) while the surrounding control flow — order, stopping
  conditions, data plumbing — stays in code. This guarantees Stage 2 can never run before
  Stage 1 finishes, or on the wrong run.
- **Stage 3 stays a `vinu-agent` tool** (`TradePlanTool`), because it's genuinely on-demand and
  parameterized per request (intraday/daily/swing timeframe) — unlike Stages 0–2, which are
  one-shot events at strategy-approval time, Stage 3 is naturally interactive, so the existing
  tool-in-chat-loop pattern is the right fit and shouldn't move into the deterministic pipeline.

The result: `vinu-research`'s service becomes the single "propose a strategy" entry point that
internally runs Stages 0→1→2 to completion (or fails/stops) before a strategy is promotable via
the existing approve endpoint. `vinu-agent` only ever sees the *result* of that pipeline
(pass/fail plus comparison angles) as data to feed into Stage 3 playbooks or conversational
summaries — it never has to orchestrate the pipeline itself.

## Roadmap at a glance

See [01-plan-overview.md](01-plan-overview.md) for the full phased breakdown. In short:

| Phase | Delivers | Depends on |
|---|---|---|
| 1 | Monte Carlo fixed, strengthened, and properly persisted/queryable | — |
| 2 | Gate enforced inside the research refinement loop | Phase 1 |
| 3 | Structured per-iteration history storage | Phase 2 (loosely) |
| 4 | Comparative critique agent (Stage 2) | Phase 3, Phase 1 |
| 5 | Trading playbook extensions (Stage 3) | Phase 1, Phase 4 |
| 6 | End-to-end integration tests | All prior phases |

Only **Phase 1** is currently approved to start; later phases get their own review when we
reach them.
