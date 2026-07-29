# S-12: A Live-Trading Kill Switch (Build Before You Need It)

## What It Is

This is the one category of pattern found in the reference repos with **zero
current analog anywhere in `vinu_research`** — because `vinu_research` is
research-only today (`00-vision.md`'s architecture is explicit: "Live-Trading...
Zero LLM calls"). It's included here as a forward-looking item, not an urgent gap.

Vibe-Trading's `order_guard.py`/`halt.py`/`enforcement.py` implement a fail-closed
pre-trade gate for whatever component *does* place live orders:
- `halt.py`: a filesystem sentinel file (`<runtime_root>/live/HALT`) checked
  independently of the agent/LLM loop — so even a wedged or hallucinating agent
  loop cannot place an order once the sentinel exists, because the check doesn't
  depend on the loop cooperating.
- `order_guard.py`: every live order call runs, in order: mandate load/expiry
  check → halt-file check → order-intent extraction → limit checks (universe,
  instrument, quantity) → a `DENY`/`ALLOW`/`PAUSE_FOR_REAUTH` decision, with every
  decision written to an audit log and order counters incremented only on
  confirmed non-error placement.

## Why It's Required

`00-vision.md` describes a 3-environment architecture where Live-Trading is
"fully deterministic" and separate from the LLM-driven Research-Simulations layer
— which is the right design. But the document doesn't yet describe what actually
*gates* that boundary once a Live-Trading component exists: what stops an approved
strategy from firing an order it shouldn't, independent of whatever logic decided
to approve it in the first place. That's a distinct concern from "is the strategy
good" (which the whole P1-P4 research loop is about) — it's "even if something
upstream is wrong, can a human always stop live execution instantly and verifiably."

## Impact

- **If never built:** the first live-execution component you write will need to
  invent this from scratch, likely under time pressure once live trading is
  imminent — exactly the wrong time to design a safety-critical component.
- **If built ahead of time:** live execution (whenever it's added) starts with a
  fail-closed default and an instant, agent-independent kill switch, rather than
  bolting safety on after the fact.

## How to Use Effectively

1. **Don't build this now** if live execution isn't imminent — it's dead code
   until there's something for it to gate. This file exists so the pattern is
   documented and ready, not to push you toward building it prematurely.
2. When it is time: the filesystem-sentinel kill switch is the single highest-
   value piece to copy first — it's cheap (one file existence check) and, crucially,
   independent of the agent loop's own state, so it works even if the LLM/loop
   itself is stuck, crashed, or misbehaving.
3. Pair the sentinel check with an audit log (reuse **S-05**'s trace-log
   infrastructure if it exists by then) so every allow/deny decision on a live
   order is permanently recorded — that's the part regulators/auditors and your
   own post-mortems will actually want.
4. The `RiskTier`/compliance-guardrail idea in **S-07** is the natural upstream
   partner to this: S-07 stops a research goal from *drifting* toward live-
   execution language; this file stops an actual order from firing even if
   something upstream approved it incorrectly. Build S-07's guardrail first (it's
   cheap and useful immediately); build this when live execution is actually on
   the roadmap.

## Implementation Hint — Where This Fits Today

**Correction to the "no current analog" framing above: live execution is not
hypothetical here — it already exists as a real, small component, and it has no
guard at all yet.** `vinu-components/vinu-live/vinu_live/` is a separate package
(not part of `vinu_research`) with:
- `execution.py` (136 lines) — TWAP/VWAP order-slicing math only (no broker calls
  here, purely quantity-splitting logic).
- `scheduler.py` (262 lines) — `LiveScheduler` class; `_execute_plan()` (around
  `scheduler.py:204-246`) is the actual order-submission code, POSTing to
  `{agent_api_url}/broker/order` (`scheduler.py:211`) for each slice.
- **Confirmed by direct grep:** no `halt`, `guard`, `circuit_breaker`, or
  `pre_trade` check anywhere in `execution.py` or `scheduler.py` — orders go
  straight from the execution plan to the broker POST with nothing in between.

**This changes the priority of this suggestion:** it's not "design a pattern for
someday" — it's "there is a real, already-shipping order-submission function
(`scheduler.py`'s `_execute_plan`) with no gate in front of it right now." Whether
that's urgent depends on whether `vinu-live` is already trading real money or
still in a dry-run/paper phase — that's the first thing a new agent picking this
up should establish before scoping the work, since it changes this from
"nice-to-have hardening" to "check this isn't already a live gap."

**Entry point if this is picked up:** `scheduler.py`'s `_execute_plan()`, right
before the loop that POSTs to `/broker/order` — add a halt-file check
(`Path(runtime_root) / "HALT"`, `.exists()`) as the very first line of that
method, independent of anything upstream. That single check is >80% of the value
described in this file and is a five-line change.

## Potential Bugs to Watch For While Testing

- **Checking the halt file once at the top of `_execute_plan()` isn't enough for
  a multi-slice plan.** TWAP/VWAP plans submit multiple slices over a time window
  (`schedule_slice_delays()` spaces them by up to `total_window_minutes`). If the
  halt check only runs before the *first* slice, a halt triggered mid-plan
  doesn't stop the remaining slices. Test triggering the halt file *between*
  slice submissions (not just before the plan starts) and confirm remaining
  slices are actually skipped, not just the next full plan.
- **TOCTOU (time-of-check-to-time-of-use) gap.** There's an unavoidable small
  window between checking `.exists()` and the POST actually firing. Test whether
  this window matters at this system's actual order-submission latency — for
  slow/sequential slice submission it's likely fine, but confirm rather than
  assume.
- **The check only protects this one code path.** If there's more than one way
  an order can reach the broker (e.g. a manual/CLI order path in
  `vinu_live/cli.py`, separate from the scheduler), test that a halt actually
  stops *all* of them — a kill switch that only some code paths respect gives
  false confidence. Grep for every place that calls the broker order endpoint
  before considering this done.
- **Silent abandonment vs. logged abandonment.** When a halt cancels remaining
  slices mid-plan, test that this is logged/recorded somewhere distinguishable
  from "plan completed normally" — an operator needs to be able to tell "this
  plan was halted with N slices unexecuted" apart from "this plan finished," or
  the halt itself becomes a source of confusing partial-fill state.
