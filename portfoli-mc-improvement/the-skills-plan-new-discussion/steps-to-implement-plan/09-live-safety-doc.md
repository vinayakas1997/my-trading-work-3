---
name: 09-live-safety-doc
status: Done
phase: 4
code: B5
depends_on: [01-verification-pass]
unlocks: []
---

# Step 09 — Live-Safety Unification Doc

## Why this step

We found two separate, real safety mechanisms while sweeping the codebase,
built independently, never documented together: `vinu-research/promotion.py`'s
BENCHING→ACTIVE bar (a statistical gate — deflated Sharpe + true
out-of-sample holdout — applied *before* a strategy goes live), and
`vinu-portfolio/circuit_breakers.py`'s `PortfolioDrawdownMonitor` (an
operational kill-switch that halts trading via `agent-api`'s `/broker/halt`
— applied *during* live operation). `promotion.py`'s own docstring claims
there's no live/paper-trading shadow account yet. Nobody has written down
how these two gates relate, or what the gap between them actually is.

**Step 01 (Findings §4) found this claim is only half right.** A real,
functional `ShadowEvaluator` class exists at `vinu_live/shadow_evaluator.py`
— it fetches BENCHING artifacts from vinu-research, computes paper-trading
Sharpe from `agent-api`'s `/broker/performance/{artifact_id}`, and
auto-promotes BENCHING → ACTIVE when paper performance holds up. But
grepping every `vinu-*` service shows nothing calls it —
not `LiveScheduler.cycle()`, not `cli.py`, not any route in `server/app.py`.
**It's real, working code that is simply never invoked.** The gap isn't
"no shadow account exists," it's "the shadow account gate is built but not
wired into anything that runs it."

## What we're achieving

One short, accurate document describing the full live-safety chain as it
actually exists: research promotion bar → **`ShadowEvaluator` (built, real,
but not scheduled/invoked anywhere)** → live circuit breaker. Explicit
about what's covered, what's built-but-dormant, and what genuinely doesn't
exist, so nobody — human or agent — assumes more (or less) safety exists
than actually does.

## Where it matters in the future

This becomes the reference anyone (including a future version of this
plan, tackling Focus 3) checks before assuming a strategy is safe to run
with real capital. Getting this wrong in either direction is bad: overstate
the safety net and something under-vetted goes live; understate it and
useful existing protections get needlessly rebuilt.

## How it connects to other steps

- **Depended on Step 01 — now resolved (see Findings §4).**
  `routes_broker.py` was read directly: `/broker/halt`/`/broker/resume`/
  `/broker/status` are real, backed by `broker/kill_switch.py`, and
  `/broker/order` deliberately reuses the same `OrderGuard` checks as the
  LLM's own order tool (routes_broker.py:101-107), so no caller can bypass
  the safety layer through a second code path. The original
  `circuit_breakers.py`-docstring-based claim was accurate. Additionally,
  `vinu-live/shadow_evaluator.py`'s `ShadowEvaluator` class was found —
  real, working BENCHING→ACTIVE paper-trading promotion logic that is
  simply never invoked anywhere (not in `LiveScheduler.cycle()`, `cli.py`,
  or `server/app.py`). This document's stage diagram must show three
  stages, not two: promotion bar → `ShadowEvaluator` (built, dormant) →
  circuit breaker.
- **Feeds Focus 3 more broadly** (Step 10) — a progressive daily portfolio
  that allocates real capital needs to know exactly where the safety net
  starts and ends.

## Substeps

1. ~~Wait for Step 01's direct read of `vinu-live` and `routes_broker.py`~~
   — done, see Step 01 Findings §4.
2. Read `vinu-research/promotion.py` in full (not just the docstring
   already captured) — confirm the exact criteria for BENCHING→ACTIVE.
3. Read `vinu-portfolio/circuit_breakers.py` in full — confirm the exact
   drawdown threshold and halt mechanism.
4. Write the single document: a short narrative plus a three-stage diagram
   (promotion bar → `ShadowEvaluator` [built, not wired to any scheduler]
   → circuit breaker). Be explicit that the middle stage is code, not
   absence — the actionable gap is "nothing calls
   `ShadowEvaluator.evaluate_all()`," a wiring task, not a design-and-build
   task. Note the wiring decision itself (what should call it, how often)
   as a follow-up, not silently resolve it in this doc.
5. Cross-reference this doc from wherever Focus 3's design work happens
   (Step 10), so it isn't rediscovered from scratch there.

## What was actually built

`project-understanding/skills/live-safety/SKILL.md` — made a skill (not a
plain doc) since every other real-fact reference in this plan
(`gatekeepers`, `strategy-tags`, `governor`) is agent-consultable, and an
allocation decision needing this information is exactly the kind of thing
an agent should be able to look up at runtime, not just a human reading
the plan folder.

**The three-stage diagram substep 4 called for grew to four stages** once
`vinu_agent/server/routes_broker.py` (the actual order-level enforcement
point) was included explicitly rather than folded into the circuit
breaker's description — it's a distinct, separate real mechanism (every
order, from any caller, is forced through the same `OrderGuard` checks),
not just plumbing for Stage 3's halt call.

**A new, load-bearing finding beyond what Step 01 surfaced:** read
`vinu_portfolio/drawdown_scheduler.py` in full (substep 3) and found its
own docstring describes closing precisely the gap `ShadowEvaluator`
currently has — "the monitor and the halt transport... both existed and
were tested, but nothing ever called `monitor.update()` with a real
value. This is that caller." Then confirmed via
`vinu-portfolio/entrypoint.sh` (`vinu-portfolio monitor &` backgrounded
alongside `vinu-portfolio serve` in the foreground) that this scheduler
genuinely starts by default in the deployed container — making Stage 3
the **one stage in the whole chain confirmed live end-to-end**, not just
theoretically reachable, and a direct, in-repo precedent for exactly the
kind of fix `ShadowEvaluator` needs. Also checked and found
`ShadowEvaluator` has no test file at all — one level more dormant than
"unwired but tested," worth stating precisely rather than rounding up.

**Cross-referenced from Step 10** (`10-focus3-portfolio-intelligence.md`)
per this step's own Definition of Done — added a note there that any
capital-allocation logic inherits this chain's gap (an ACTIVE artifact
has cleared Stage 1 but never Stage 2) and must not silently treat every
ACTIVE strategy as equally trusted.

## Definition of done

- [x] Every claim in the document is backed by a direct source read —
      `promotion.py`, `circuit_breakers.py`, `drawdown_scheduler.py`,
      `entrypoint.sh`, and `routes_broker.py` all read in full.
- [x] The `ShadowEvaluator` finding is represented as "built but dormant"
      (and, newly confirmed, untested) — not folded into "exists" or
      "doesn't exist."
- [x] The acknowledged gap is stated plainly in its own section ("What
      this means in practice"), not implied.
- [x] Document is linked from Step 10's file (see below).
