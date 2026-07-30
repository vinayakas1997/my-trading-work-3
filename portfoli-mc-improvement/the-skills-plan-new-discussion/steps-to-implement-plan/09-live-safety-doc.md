---
name: 09-live-safety-doc
status: Not Started
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
— applied *during* live operation). `promotion.py`'s own docstring is
explicit that there's no live/paper-trading shadow account yet. Nobody has
written down how these two gates relate, or what the gap between them
actually is.

## What we're achieving

One short, accurate document describing the full live-safety chain as it
actually exists: research promotion bar → (gap: no shadow/paper account) →
live circuit breaker. Explicit about what's covered and what genuinely
isn't, so nobody — human or agent — assumes more safety exists than
actually does.

## Where it matters in the future

This becomes the reference anyone (including a future version of this
plan, tackling Focus 3) checks before assuming a strategy is safe to run
with real capital. Getting this wrong in either direction is bad: overstate
the safety net and something under-vetted goes live; understate it and
useful existing protections get needlessly rebuilt.

## How it connects to other steps

- **Depends on Step 01** — the `vinu-live`/`routes_broker.py` claims in
  this doc currently rest on a comment in an unrelated file
  (`vinu-portfolio/circuit_breakers.py`'s docstring), not a direct read.
  Do not finalize this document until Step 01 confirms it directly.
- **Feeds Focus 3 more broadly** (Step 10) — a progressive daily portfolio
  that allocates real capital needs to know exactly where the safety net
  starts and ends.

## Substeps

1. Wait for Step 01's direct read of `vinu-live` and `routes_broker.py`.
2. Read `vinu-research/promotion.py` in full (not just the docstring
   already captured) — confirm the exact criteria for BENCHING→ACTIVE.
3. Read `vinu-portfolio/circuit_breakers.py` in full — confirm the exact
   drawdown threshold and halt mechanism.
4. Write the single document: a short narrative plus a simple stage
   diagram (promotion bar → [gap] → circuit breaker), explicit about the
   acknowledged gap (no shadow/paper account) rather than glossing over it.
5. Cross-reference this doc from wherever Focus 3's design work happens
   (Step 10), so it isn't rediscovered from scratch there.

## Open risks / assumptions

- Cannot be finalized before Step 01 completes its `vinu-live` read — the
  current understanding of `/broker/halt` and `OrderGuard` is secondhand.

## Definition of done

- [ ] Every claim in the document is backed by a direct source read, not a
      secondhand reference.
- [ ] The acknowledged gap (no shadow/paper account) is stated plainly,
      not implied.
- [ ] Document is linked from Step 10's file once it exists.
