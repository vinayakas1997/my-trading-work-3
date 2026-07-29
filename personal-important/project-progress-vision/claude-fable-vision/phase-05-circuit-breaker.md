# Phase 5 — Circuit Breaker / Kill Switch

Status: **not started** · Depends on: Phase 1 (risk math), Phase 3 (live book) · Blocks: Phase 6

## What it is

A hard, deterministic enforcement layer inside `vinu-live`: max daily loss, max aggregate VaR,
max greeks exposure, max position count — thresholds that halt trading regardless of what any
frozen Phase 4 plan says. Kept separate from Phase 1's general risk-math library on purpose:
Phase 1 can be extended and recalibrated freely; this phase's thresholds must require a
deliberate, reviewed change to touch, the same way the Monte Carlo gate is designed to be
un-bypassable by an agent's discretion. If the breaker lived inside the same module as general
risk computation, a change made for a good reason elsewhere in that module could accidentally
weaken it.

## Impact

**Before this phase:** Even with a well-authored Phase 4 plan, nothing stops a string of
individually-reasonable trades from compounding past a sane daily loss limit, and nothing
catches a book that looks diversified per-symbol but is actually one correlated bet via Phase
2's `shock_cluster_membership`.

**After this phase:** Every order, regardless of source, is checked against hard limits
immediately before execution, using Phase 1's clustered/dynamic covariance across Phase 3's live
book — not a naive sum of independent per-symbol numbers — and trading halts, not just flags,
on breach.

**What still won't work after this phase alone:** The breaker only matters once Phase 6's
execution engine calls it on every single order path.

## Where changes occur

- `vinu-live`'s enforcement module — reads Phase 3's book (current exposure, today's realized
  PnL) and Phase 1's risk numbers (current VaR, greeks, dynamic covariance) as its only inputs.
- Thresholds configured as a reviewed deployment setting, not a runtime-adjustable parameter any
  plan or forecast can influence.
- Must be the last check in Phase 6's execution path — no order reaches a broker without first
  clearing this gate.

## Why we need this — and why clustering must be checked here, not assumed elsewhere

This is the single most important gap in the whole vision: everything else here is about doing
things well; this phase is about making sure a mistake anywhere upstream — a miscalibrated
forecast, an incomplete contingency rule, a correlation blind spot — cannot compound into an
account-ending loss. Critically, "max aggregate VaR" is only a real limit if it's computed from
Phase 1's dynamic covariance across everything held, not summed per-symbol: a book of five
positions that each look small and independent can be one large correlated bet on a shared shock
day if they belong to the same Phase 2 cluster group. A breaker that only sums independent
numbers would pass every test on calm, uncorrelated synthetic data and still fail exactly when a
real cluster shock hits — the one scenario this phase exists for.

## How to test it

- Threshold test: synthetic book states that approach and then exceed each limit correctly
  transition from "trading allowed" to "halted" at the configured threshold, not before or
  after.
- Clustered-exposure test: seed a book of positions individually within limits but belonging to
  the same Phase 2 shock cluster; confirm the breaker's aggregate check — using Phase 1's
  dynamic covariance — identifies the combined exposure as over-limit where a naive per-symbol
  sum would not.
- Bypass test: confirm no code path (Phase 6's execution engine, a manual override, a direct API
  call) can place an order without this check executing first.
- Recovery test: once halted, trading only resumes via an explicit, logged reset action, never
  automatically on the next tick.
