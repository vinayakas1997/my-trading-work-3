---
name: gatekeepers
description: Evaluation vocabulary for judging a backtest/strategy result across multiple angles (sample size, risk-adjusted return, drawdown stability, robustness). Thresholds live in rules.yaml.
category: tool
---

## Gatekeepers — Multi-Angle Result Evaluation

A "gatekeeper" is one formal check applied to a strategy result. Each gatekeeper
looks at the result from a different angle (sample size, risk-adjusted return,
drawdown stability, robustness, cost realism, etc.) and returns pass/fail plus
a severity.

This skill is the shared evaluation vocabulary. It does not run the Monte
Carlo sweep itself — `optimizer-rules` (and later the daily portfolio, and
live monitoring) consume it by referencing gatekeeper `id`s.

### How to use this skill

1. Load `rules.yaml` via `load_support_file("rules.yaml")`.
2. For a given strategy result, evaluate each gatekeeper's `check` against the
   result's metrics.
3. Severity determines what a failure means:
   - `hard` — reject the result outright. Do not consider it a candidate.
   - `soft` — down-weight it. Note the failure but keep it in the running if
     nothing else disqualifies it.
4. A result "passes gatekeeping" only when all `hard` gatekeepers pass. Report
   `soft` failures alongside the verdict so the agent (or a human) can weigh
   them.

### Angles currently covered

- `sample_size` — is there enough trade history to trust the numbers?
- `risk_adjusted_return` — is the return good relative to the risk taken?
- `risk_stability` — does risk (drawdown) hold up out-of-sample?
- `robustness` — does performance survive small parameter perturbations?
- `cost_realism` — does the result account for realistic costs/slippage?
- `benchmark_relative` — does it actually beat a naive benchmark (buy-and-hold, SPY)?

These angles come directly from the research-workflow lessons in
`portfoli-mc-improvement/info-1.pdf` (small-sample bias, parameter
sensitivity, walk-forward validation, realistic costs, benchmark comparison)
and the existing hard-gate checklist in `backtest-diagnose/SKILL.md`. New
gatekeepers should declare which angle they belong to — don't invent a new
angle without a reason.

### Adding a new gatekeeper

Add an entry to `rules.yaml` with a unique `id`, the `angle` it belongs to, a
`check` expressed in terms of result metrics, a `severity`, and a short
`reason`. Do not hardcode thresholds anywhere else — this file and its
`rules.yaml` are the single source of truth.
