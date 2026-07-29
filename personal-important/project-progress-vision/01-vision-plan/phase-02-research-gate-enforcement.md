# Phase 2 — Wire the Gate Into the Research Refinement Loop

Status: **not started** · Depends on: Phase 1 · Blocks: (feeds Stage 1's real behavior; loosely feeds Phase 3)

## What it is

Makes the Monte Carlo gate from Phase 1 mandatory rather than optional inside
`vinu-research`'s refinement loop — this is the literal implementation of "a new strategy
proposed for a ticker must first be validated with an initial Monte Carlo run before anything
else proceeds." Phase 1 made validation *possible and correctly persisted*; Phase 2 makes it
*enforced* every time the research loop runs.

Today, `StrategyResearchLoop.run()` (`vinu-research/vinu_research/loop.py`) already generates
a strategy, backtests it via HTTP call to `vinu-simulator`, runs it through a rule-based +
LLM risk critic, and iterates until PASS/STOP/pivot/max-iterations. But
`ResearchTools.run_backtest()` (`vinu-research/vinu_research/tools.py`), which makes that HTTP
call, never sets `run_validation=True` — so even after Phase 1, the research loop still
wouldn't request a Monte Carlo check unless explicitly told to.

## Impact

**Before this phase:** Even with Phase 1 shipped, nothing in the research loop asks for
Monte Carlo validation. A strategy can sail through all iterations and reach PASS purely on
Sharpe/drawdown/win-rate thresholds, with no statistical-significance check at all.

**After this phase:** Every backtest the research loop runs — starting with iteration 1 —
includes a Monte Carlo validation request. If the very first backtest fails the combined
verdict from Phase 1's `compute_validation_verdict()`, the loop stops immediately with a new
terminal status (`MC_GATE_FAILED`) instead of spending iteration budget refining a strategy
that hasn't even cleared the significance bar. On later iterations, the validation verdict also
becomes an input to the risk critic — a strategy can no longer reach `PASS` on metrics alone if
it's failing the Monte Carlo check.

**What still won't work after this phase alone:** The rich "what was tried across iterations"
history is still not durably queryable (that's Phase 3) — this phase only affects whether
validation gates iteration acceptance, not how iteration history is stored.

## Where changes occur

- `vinu-research/vinu_research/tools.py`
  - `ResearchTools.run_backtest()` (lines ~46-101): default to `run_validation=True` in the
    POST body to `/simulate/custom`. Keep it as an explicit parameter (not hardcoded deep in
    the payload construction) so tests can still call it with `False` for speed where the
    Monte Carlo check isn't the thing under test.

- `vinu-research/vinu_research/loop.py`
  - `_run_backtest` (lines ~589-612): pass `run_validation=True` through to
    `ResearchTools.run_backtest()`.
  - Immediately after the *first* backtest result comes back (iteration 1, before entering the
    refine loop), read `result["validation"]` (now populated per Phase 1) and evaluate
    `compute_validation_verdict(...)`. If it fails, short-circuit `run()`: extend the existing
    verdict/status vocabulary used in the stopping-condition logic (currently
    `PASS`/`REFINE`/`STOP`/pivot, checked around lines 407-462) with a new `MC_GATE_FAILED`
    status, and persist that outcome instead of proceeding into iteration 2+.
  - `_risk_critic` (called at lines ~347-350): the validation verdict, recomputed each
    iteration (since refinements change the trade sequence and thus the Monte Carlo result),
    becomes an additional input.

- `vinu-research/vinu_research/llm.py`
  - `_build_risk_critic_prompt` (lines ~32-85) and `_rule_based_check`
    (`loop.py` lines ~1245-1419): add the Monte Carlo verdict as an explicit rule. Even if
    Sharpe/drawdown/win-rate all look good, a Monte Carlo failure keeps the verdict at
    `REFINE`. The existing rule that "the LLM enhancement step can only add suggestions or
    upgrade REFINE→PASS/STOP, never downgrade" needs one exception: an MC-gate failure is a
    hard floor no LLM upgrade can override.

## How to test it

- `vinu-research/tests/` (mirror existing test structure for `loop.py` — check current
  coverage first): a test asserting that when the mocked `run_backtest` response includes a
  failing `validation` verdict on iteration 1, `run()` terminates with `MC_GATE_FAILED` and
  never calls the refinement/generation step for iteration 2.
- A test asserting that `_risk_critic`'s rule-based check downgrades an otherwise-PASS-worthy
  metrics profile to `REFINE` when the Monte Carlo verdict fails, and that the LLM-enhancement
  mock cannot upgrade past that floor.
- A regression test on `ResearchTools.run_backtest()` confirming the POST body to
  `/simulate/custom` includes `"run_validation": true` by default.
- Manual/integration check: run the research loop against a synthetic strategy known to
  produce a random-looking trade sequence (e.g. randomly generated signals) and confirm it's
  rejected at the gate rather than being refined for several iterations first.
