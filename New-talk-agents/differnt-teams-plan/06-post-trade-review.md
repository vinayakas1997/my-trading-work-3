---
name: team-post-trade-review
status: proposed-not-built
purpose: design proposal for a new vinu-agent team that reflects on a CLOSED trade -- "how it should have been" -- and feeds what it finds back into the strategist team for the next cycle. The second of two teams that don't fit the plain user-triggered delegate_to_team shape.
---

# post_trade_review (proposed)

## Role

After a position closes, compare what actually happened to what was
predicted when the trade was opened, and write down *why* — not just the
win/loss number (`pnl_attribution` the angle already does that), but which
part of the original reasoning held up and which didn't.

## This team's trigger already exists in the project — it isn't invented here

A real trade close already fires a real event: `POST
/pnl-attribution/{symbol}/record`, confirmed directly against
`New-talk-/04-enhancement-of-each-angle/22-pnl_attribution.md` (itself
checked against the real schema in `vinu-live/vinu_live/book/schema.py`
and `vinu_initial_analysis/pnl_attribution_ingest.py`). Every closed
`Position` already carries an `artifact_id` linking back to the Phase 4
trade-plan artifact that authored it — exactly the link this team needs to
know what was actually predicted, without inventing a new position-close
signal or a new way to find the original strategy.

`post_trade_review` rides that same event: whatever handler already calls
`pnl_attribution`'s record endpoint is the natural place to also construct
`TeamManager` directly (same non-orchestrator pattern as `trade_monitor`,
see [00-overview.md](00-overview.md)) and kick off a review run, keyed by
the position/`artifact_id`.

## Scope & responsibilities

- **In scope**: one closed position; pull the original strategy spec via
  its `artifact_id` link; pull the angle data as of both entry and exit;
  compare predicted vs. actual (direction, magnitude, timing); write a
  short "what held up / what didn't / what we'd do differently" reflection
  grounded in the real angle numbers on both ends, not vibes.
- **Explicitly not in scope**:
  - Recomputing win/loss stats — that's `pnl_attribution`'s job, already
    real and already correctly implemented per its design doc (win rate,
    avg win/loss %, proper confidence intervals). This team adds the
    per-trade narrative that doc explicitly says is missing; it doesn't
    duplicate the aggregate math.
  - Automatically changing anything — its output is lessons that flow to
    `strategist` for the *next* proposal on that symbol/setup, not a
    write to any live strategy. Feedback, not autopilot.

## How it adopts to vinu-agent, out of the box

Manager + specialist(s), `TEAM.md`/`AGENT.md`, invoked the same
non-orchestrator way as `trade_monitor` — constructed directly via
`TeamManager` by whatever already handles the position-close event, not
via `delegate_to_team`. No new vinu-agent mechanism; the trigger is a real
event that already exists elsewhere in the project.

## Position in the DAG

Runs once, right after `trade_monitor` hands off (position closed).
Output loops back to `strategist` as input for the next cycle on that
symbol — see [00-overview.md](00-overview.md).

## Open questions

- Exact tool to fetch "angle data as of entry" — angle history is
  presumably queryable by `run_id`/timestamp already (per `AngleStorage`'s
  real `run_id`-based "latest" resolution), but a specialist-facing tool
  for "angles as of a specific past timestamp" doesn't exist yet; likely
  new, likely small.
- Where do lessons actually land for `strategist` to pick up — a new
  field on the strategy-spec schema (open question in
  `02-strategist.md`), a separate lessons store, or just plain text a
  human skims before the next `strategist` run? Not decided.
