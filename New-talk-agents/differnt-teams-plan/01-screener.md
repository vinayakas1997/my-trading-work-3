---
name: team-screener
status: built
purpose: role/scope reference for the screener team, for consistency with the rest of this folder's team docs. The real source of truth is the actual TEAM.md and the build log, both linked below — this file doesn't duplicate them, just places screener in the lifecycle DAG.
---

# screener

Real files: [teams/screener/](../../vinu-components/vinu-agent/teams/screener/)
(`TEAM.md`, `manager_prompt.md`, `agents/angle_synthesizer/`). Build +
real-LLM test results: [../implementation/00-status.md](../implementation/00-status.md).

## Role

Given a watchlist, produce one honest, evidence-grounded initial read per
symbol by pulling together every vinu-initial-analysis angle for that
symbol — instead of each angle sitting in its own file with nothing ever
looking across all of them for one symbol.

## Scope & responsibilities

- **In scope**: fetch all angles for each symbol (`get_all_angles` tool),
  report how many actually have data (`row_count > 0`), cite real numbers
  from the ones that do, say plainly when most/all angles are still empty.
- **Explicitly not in scope**: proposing a trade, a strategy, or an
  entry/exit rule. Screener's job ends at "here's what the data currently
  shows" — turning that into an actionable strategy is `strategist`'s job,
  one step later in the DAG, on purpose (keeps the specialist prompt
  narrow and keeps "what does the data say" separate from "what should we
  do about it").
- Manager delegates once per ticker in the watchlist; one specialist role
  (`angle_synthesizer`) per delegation.

## How it adopts to vinu-agent, out of the box

Manager + one specialist, `TEAM.md` + `agents/angle_synthesizer/AGENT.md`,
invoked via `delegate_to_team` from an orchestrator turn — no new
mechanism needed. Confirmed working against a real local LLM: 7/7 real
LLM calls succeeded, both specialist delegations completed with real
content, though the manager's own final synthesis was found to be
unreliable in that specific run (see the build log's real-test findings)
— a model-reliability question, not a mechanism gap.

## Position in the DAG

First step. Feeds `strategist` — see [00-overview.md](00-overview.md).
