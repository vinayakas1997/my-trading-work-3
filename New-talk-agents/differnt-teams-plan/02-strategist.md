---
name: team-strategist
status: proposed-not-built
purpose: design proposal for a new vinu-agent team that turns a screener-style angle read into a concrete, structured strategy spec for one symbol.
---

# strategist (proposed)

## Role

Take one symbol's angle data (the same kind `screener` already gathers)
and propose a *concrete* strategy: an entry rule, an exit rule, a stop,
and a position-sizing approach — grounded specifically in which angles
actually have data, not a generic template. `screener` answers "what does
the data show"; `strategist` answers "given that, what would we actually
do."

## Scope & responsibilities

- **In scope**: one symbol at a time; read angle data (reuse
  `get_all_angles`, same tool `screener` already uses); output a
  structured strategy spec, not prose alone — every field traceable to a
  specific angle's real numbers (e.g. "stop at 1.5x ATR" only if an ATR-
  producing angle actually has data, not invented).
- **Explicitly not in scope**:
  - Parameter tuning / backtesting the spec it proposes — that's
    `strategy_tuner`'s job, deliberately kept separate so `strategist`
    doesn't need Monte Carlo tooling and `strategy_tuner` doesn't need to
    re-derive *which* angles justify a strategy shape.
  - Approving the strategy against portfolio risk — that's
    `risk_gatekeeper`'s job.
  - If most angles for a symbol are empty (the real, current state per
    the screener test — `vinu-initial-analysis` has no data yet), the
    honest output is "not enough data to propose a strategy for this
    symbol yet," not a confident-sounding guess. Same discipline the
    `angle_synthesizer` prompt already enforces for `screener` — worth
    keeping consistent rather than reinventing per team.
- A **strategy spec** needs an explicit shape agreed before this is built
  — not decided here, but a reasonable minimum: `symbol`, `direction`
  (long/short), `entry_condition`, `exit_condition`, `stop_loss`,
  `position_size_rule`, `angles_used` (list, for traceability), `angles_
  missing` (list, so the gap is explicit downstream too). Whatever this
  ends up as, `strategy_tuner` and `risk_gatekeeper` both consume it
  directly, so its shape should be settled once, here, before any of the
  three teams are built.

## How it adopts to vinu-agent, out of the box

Same shape as `screener`: one manager, one specialist (`strategy_writer`
or similar), `TEAM.md` + `agents/*/AGENT.md`, invoked via
`delegate_to_team` from an orchestrator turn or chained directly after a
`screener` run. No new mechanism — reuses `get_all_angles` as-is; the only
new thing is the specialist's prompt (turn a read into a spec) and
agreeing on the spec's JSON shape above.

## Position in the DAG

Second step, after `screener`. Can also be seeded by a validated idea from
`research` (the offline exploratory team) instead of starting from a
screener read — see [00-overview.md](00-overview.md)'s DAG. Feeds
`strategy_tuner`.

## Open questions

- Exact strategy-spec schema (above) — needs to be pinned down before
  `strategist`, `strategy_tuner`, and `risk_gatekeeper` can all be built
  against it consistently.
- Does `strategist` ever run on more than one symbol per delegation (like
  `screener`'s per-ticker loop), or always one-at-a-time? Leaning
  one-at-a-time, since a strategy spec is inherently per-symbol and
  batching would just mean the manager loops the same way `screener`'s
  does — not decided.
