---
name: team-research
status: built
purpose: role/scope reference for the research team, for consistency with the rest of this folder's team docs. Real source of truth is TEAM.md and the architecture doc, both linked below.
---

# research

Real files: [teams/research/](../../vinu-components/vinu-agent/teams/research/)
(`TEAM.md`, `manager_prompt.md`, `agents/idea_generator/`,
`agents/backtest_runner/`, `agents/risk_critic/`). Design rationale:
[../01-orchestrator-and-teams-architecture.md](../01-orchestrator-and-teams-architecture.md#research-team-first-team-replaces-vinu-research).

## Role

Offline / exploratory idea generation: generate a candidate strategy idea,
backtest it via `vinu-simulator`, risk-critique it, iterate until
`VERDICT: PASS` or `STOP`. Replaces the old standalone `vinu-research`
service's loop.

## Scope & responsibilities

- **In scope**: open-ended strategy exploration, not tied to a specific
  symbol's current angle data the way `strategist` is — closer to
  "brainstorm and validate an idea" than "read this symbol and propose
  something."
- **Explicitly not in scope**: doesn't read vinu-initial-analysis angle
  data at all today (`backtest_runner` calls `vinu-simulator` directly,
  unchanged from the old `vinu-research` behavior) — a real gap relative
  to the newer angle-aware teams in this folder, not yet closed.

## How it adopts to vinu-agent, out of the box

Manager + 3 specialists (`idea_generator`, `backtest_runner`,
`risk_critic`), `TEAM.md`/`AGENT.md`, invoked via `delegate_to_team`. Uses
the `run_backtest` tool (calls `vinu-simulator`'s `/simulate/custom`).

## Position in the DAG

Sits alongside the main screener→strategist→tuner→gatekeeper pipeline as
an optional, offline seed — a `research`-validated (PASS) idea can feed
`strategist` directly instead of `strategist` always starting from a fresh
`screener` read. See [00-overview.md](00-overview.md).

## Open question

Should `research`'s `idea_generator` be updated to read angle data too
(via `get_all_angles`, the same tool `screener`/`strategist` use), so
research-generated ideas are grounded the same way angle-driven ones are —
or is staying angle-blind actually the point (pure idea exploration,
unconstrained by what data happens to exist yet)? Not decided.
