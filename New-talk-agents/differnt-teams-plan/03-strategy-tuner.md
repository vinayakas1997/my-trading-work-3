---
name: team-strategy-tuner
status: proposed-not-built
purpose: design proposal for a new vinu-agent team that takes a strategist-produced strategy spec and tunes its parameters via real Monte Carlo / walk-forward backtests, not LLM-guessed numbers.
---

# strategy_tuner (proposed)

## Role

Given a strategy spec (from `strategist`, or a validated idea from
`research`), improve its parameters (stop distance, sizing, entry
threshold, ...) by actually running backtests against real historical
data and reading back real metrics — Sharpe, drawdown, hit rate, sample
size `n` — not by having the LLM invent plausible-sounding numbers.

## The load-bearing design decision

**The Monte Carlo / parameter sweep itself must be real, deterministic
Python — not something the LLM computes.** This was flagged directly
after the real screener-team test: per-call LLM latency on the local
model in use ranged 14.77s–276.44s (see
`../implementation/00-status.md`'s real-test notes). An optimizer that
round-trips through the LLM once per parameter trial would take hours for
a sweep that should take seconds. So:

- A new tool (`run_parameter_sweep` or similar, exact name TBD) runs an
  *entire* sweep internally in one call — e.g. a grid or Monte Carlo
  sample over 2–3 parameters, N backtests each — and returns a compact
  results table (best few combinations + their metrics), not one
  combination at a time.
- The LLM's job is narrower and cheaper: decide which parameter *region*
  to explore (or accept the sweep's own top result), interpret whether the
  improvement is real or noise given `n`, and decide when to stop
  iterating — a handful of LLM calls total per tuning run, not one per
  trial.
- This tool should sit on top of the walk-forward backtest harness from
  the separate, in-progress shared-backtest-infrastructure plan
  (`run_walk_forward` in `vinu-tools/vinu_tools/compute/backtest/`,
  currently mid-build) rather than reimplementing its own sweep/backtest
  loop — that harness is exactly "run this strategy shape across history
  and score it," which is what a sweep is doing N times over.

## Scope & responsibilities

- **In scope**: takes one strategy spec in, returns a tuned strategy spec
  out (same shape as `strategist` produces, with updated parameter values
  and the metrics that justify them attached).
- **Explicitly not in scope**: inventing a new strategy shape (that's
  `strategist`'s job — `strategy_tuner` only ever tunes parameters within
  a spec it was handed, it doesn't redesign entry/exit logic) or approving
  the result for live use (`risk_gatekeeper`'s job, next in the DAG).
- Every improvement claim must carry its sample size — same rule the
  shared-backtest-infrastructure plan already commits to for every
  rate/average it produces ("every rate/average must carry its `n`") —
  worth reusing verbatim here rather than restating a weaker version.

## How it adopts to vinu-agent, out of the box

Manager + specialist(s), same `TEAM.md`/`AGENT.md` convention, invoked via
`delegate_to_team`. The only genuinely new piece is the
`run_parameter_sweep` tool itself (new Python, wraps the walk-forward
harness) — the team mechanism, delegation, logging, and run-tracking are
all reused unchanged.

## Position in the DAG

Third step, after `strategist`. Feeds `risk_gatekeeper`. See
[00-overview.md](00-overview.md).

## Open questions

- Depends on the shared backtest infrastructure plan (walk-forward
  harness) actually landing first — this team can't be built for real
  before `run_walk_forward` exists, though its `TEAM.md`/prompts could be
  scaffolded earlier against a stub.
- How many tuning rounds before stopping — a fixed iteration budget (same
  pattern as the manager/orchestrator budgets already in the architecture
  doc) or a convergence check (stop when the last round's improvement is
  within noise given `n`)? Not decided.
