# Phase 7 — Family-Wise Overfitting Control & Parameter-Surface Robustness

Status: **not started** · Depends on: Phase 1, Phase 4 · Blocks: —
(Advanced vision — see [02-advanced-vision.md](02-advanced-vision.md))

## What it is

Two related upgrades to how "is this a real edge or noise" is judged, both aimed at the same
failure mode: a strategy that looks statistically significant only because of how it was
found, not because the effect is real.

**7a — Family-wise overfitting control.** `vinu-research/vinu_research/comparison.py`'s
`rank_candidates()` already deflates Sharpe to account for the number of candidates (`n_trials`)
generated *within a single research run*. But if a ticker has been researched across 50
separate runs over a year, the true multiple-comparisons correction needs the *lifetime* trial
count for that ticker — otherwise Stage 0/1 will keep passing strategies that are statistically
expected to appear by chance given how many total shots have been taken at that symbol, even
though each individual run's internal deflation looks fine.

**7b — Parameter-surface robustness.** Stage 0's Monte Carlo (`monte_carlo_permutation`,
`block_bootstrap_permutation`, `price_path_resample` — Phase 1) all test robustness of a
*single tested parameter point's* trade sequence/price path. None of them ask "does this
strategy still work if I nudge RSI period from 14 to 13, or the threshold from 0.70 to 0.68?"
A strategy that passes only at an exact parameter point and fails at small perturbations is a
knife-edge overfit — the backtest optimizer effectively curve-fit to noise at that one point.

## Impact

**Before this phase:** A strategy that's the 40th thing tried on a ticker, or that only works
at one precise parameter setting, can still reach PASS through Phases 1–4 with no signal that
either of these red flags is present.

**After this phase:** Every promotion decision accounts for how many strategies have ever been
tried on this ticker (not just this run), and every PASS comes with a documented robustness
plateau — the range of nearby parameter values that also pass, not just the single winning
point.

## Where changes occur

- `vinu-research/vinu_research/storage/sqlite_backend.py` — add a lifetime trial counter per
  symbol (e.g. a `symbol_trial_counts` table or a derived count from `research_iterations`
  across all `research_runs` for that symbol, from Phase 3's storage). `comparison.py`'s
  deflated-Sharpe computation takes this lifetime count as `n_trials` instead of (or in addition
  to) the within-run count.
- `vinu-research/vinu_research/comparison.py` — `rank_candidates()` (or a new
  `family_wise_deflated_sharpe()`) accepts the lifetime trial count and recomputes the
  correction. This directly affects whether Stage 1's PASS verdict is granted.
- New robustness-check step, likely in `vinu-research/vinu_research/loop.py` right after a
  candidate reaches PASS but before it's accepted as the final winner: re-run the backtest at a
  small grid of parameter perturbations around the winning point (e.g. ±1 step on each numeric
  parameter in the strategy's config) via the existing `_run_backtest` HTTP path, and require a
  minimum fraction of the neighborhood to also pass Stage 0's validation verdict. Store the
  robustness surface (parameter deltas → pass/fail + Sharpe) alongside the iteration record
  (Phase 3's `research_iterations`, or a new `robustness_surface` JSON column on the winning
  iteration).
- `vinu-agent/vinu_agent/tools/trade_plan_tool.py` (Phase 5) — surface the robustness result
  as a playbook caveat ("this strategy's edge is narrow — small parameter drift may break it"
  vs. "robust across a wide parameter range").

## How to test it

- Unit test: seed a symbol with a large lifetime trial count and confirm
  `family_wise_deflated_sharpe()` produces a materially harsher correction than the
  within-run-only calculation for the same candidate.
- Unit test: a synthetic strategy engineered to work only at one exact parameter value (e.g. a
  lookback that happens to align with a specific pattern in synthetic test data) should fail
  the robustness-plateau check even though its single-point backtest passes Stage 0.
- Integration test: a genuinely robust synthetic strategy (works across a range of nearby
  parameters) should pass both checks.
