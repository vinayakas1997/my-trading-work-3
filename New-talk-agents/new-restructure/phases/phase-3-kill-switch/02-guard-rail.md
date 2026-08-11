---
name: phase-3-guard-rail
status: proposed-not-built
purpose: what keeps the Kill Switch a real, trustworthy gate -- scope correctness, fail-closed direction, and not blocking things that should keep running during a halt.
---

# Phase 3 -- Guard rails

**A third, distinct fail-closed direction: on any uncertainty about the
Kill Switch's state, assume halted.** This plan already has two other
fail-closed defaults pointing opposite ways for good reasons (Phase 0's
RunLog trigger fails toward "skip," because the only cost is a wasted LLM
call; the change-gate fails toward "run anyway," because skipping risks
hiding a real change). This one is different again: if `GET
/broker/status` errors or times out, `capital_allocator` must treat that
as **halted**, not as "not halted." This is the one check in the whole
design where the wrong default risks real money moving when it shouldn't
-- the safe direction is unambiguous here in a way it isn't for the other
two.

**Scope matching must be exact, and tested as its own thing.** `scope`
defaults to `None` (global halt, blocks everything) but can be a specific
string (halt one symbol/strategy only). Whoever calls `/broker/halt` and
whoever later checks `/broker/status` must agree on what a scope string
*is* -- ticker symbol, `artifact_id`, or something else -- or a halt
issued at one granularity could silently fail to block an action checked
at a different one. Pin this down as a single, documented convention
before implementing either side.

**`PENDBLOCK` must auto-retry on resume, not require a manual nudge.**
Same visibility requirement as `PEND` from Phase 2 (every transition
writes a `TickerLedger` row), plus one more: once the Kill Switch is
resumed, `PENDBLOCK` artifacts are automatically re-attempted on the
*next* cadence run, exactly like ordinary `PEND` items -- no separate
"unstick this" action required. A halt that resolves itself shouldn't
leave funded-but-blocked artifacts stranded because nobody remembered to
re-trigger them by hand.

**The check-then-act race is real and not fully closeable -- minimize it,
don't pretend to eliminate it.** Checking `/broker/status` and then
calling `mark_active` are two separate network calls; a halt engaged in
the gap between them could theoretically slip through. Keep the gap as
small as possible (check immediately before the funding call, not
earlier in the cadence run), but this plan does not attempt a distributed
lock across services to close the window entirely -- halts are rare,
deliberate events, and the residual race window is an accepted, stated
limitation, not a silently ignored one.

**Blocking the rebalance-request path does not mean blocking Monitor's
own hold/decay judgment.** Only the *request* (rebalancer asking to
unwind X to fund Y) is gated by the Kill Switch -- Monitor's ordinary
read-only comparison of a live position against its shadow twin must keep
running during a halt. Visibility and decay-detection are not order-flow
actions; stopping them during a halt would mean losing exactly the
information a human needs to decide when it's safe to resume.
