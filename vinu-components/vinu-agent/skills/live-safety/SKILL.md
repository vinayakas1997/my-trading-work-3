---
name: live-safety
description: The real, verified chain between a research result and real capital — what gates exist, what's built but dormant, and what genuinely doesn't exist yet. Check this before assuming a strategy is safe to run live.
category: reference
---

## Live-Safety Chain — What Actually Stands Between Research and Real Money

Every claim below was confirmed by reading the actual source, not
inferred from a docstring or a comment in an unrelated file (that mistake
was made once already in this plan's history — see Step 01's Findings §4
— and corrected here). Four real, independently-built mechanisms exist.
They were never documented together before this file. Read this before
assuming a strategy is safe to run with real capital, and before assuming
protection exists (or doesn't) that hasn't been verified.

### The chain

```
1. Research promotion bar        2. ShadowEvaluator          3. Circuit breaker           4. Order-level enforcement
   (vinu-research)                  (vinu-live)                 (vinu-portfolio)             (vinu-agent)
   BENCHING -> eligible?            paper P&L vs.                live equity drawdown          every order, always
   statistical gate                 backtest expectation          -> kill switch                routed through the
                                     -> auto-promote                                              same guard
   [REAL, ENFORCED]                 [WORKS, NOT SCHEDULED]       [REAL, RUNNING]               [REAL, ENFORCED]
```

### Stage 1 — Research promotion bar (enforced)

`vinu_research/promotion.py::meets_promotion_bar(artifact, config, correlation_verdict)`
gates BENCHING → ACTIVE. Read in full. Checks, all required unless a
config flag disables them:
- `artifact.deflated_sharpe >= config.promotion_deflated_sharpe_threshold`
  — multiple-comparisons-corrected confidence that the best result reflects
  real skill, not luck across many trials (see Step 01 Findings §1-2 for
  why this correction matters).
- `artifact.holdout_passed` — true out-of-sample check, on data the
  refinement loop never tuned against. If holdout was never computed
  (date range too short), that itself is treated as a failure when
  `config.promotion_holdout_required` is set, not silently skipped.
- `artifact.stress_test_passed` — similarly required-or-flagged-missing,
  not silently skipped.
- The correlation gate (`vinu_research/gates/correlation_gate.py`), if a
  `CorrelationVerdict` is supplied — folded in as hard here (see
  `gatekeepers/SKILL.md` for why this same check is soft at
  candidate-evaluation time and hard here).

Enforced via `POST /research/artifacts/{id}/promote` — refuses promotion
unless `meets_promotion_bar` returns eligible, though `force=true` lets a
human override it explicitly. **This stage genuinely gates.**

### Stage 2 — ShadowEvaluator (built, not enforced — nothing calls it)

`vinu_live/shadow_evaluator.py::ShadowEvaluator` is real, working code:
fetches BENCHING artifacts from vinu-research, computes paper-trading
Sharpe from `agent-api`'s `/broker/performance/{artifact_id}`, and
auto-promotes BENCHING → ACTIVE when paper performance holds up
(`degradation <= max_sharpe_degradation`, minimum `min_paper_days` of
paper data). This is exactly the "does it hold up outside of research
before going live" check a shadow/paper-trading phase is supposed to be.

**Update (Phase 4, New-talk-agents/new-thinking/new-restructure/phases/
phase-4-live-shadow-fix/, built 2026-08-11): the endpoint claim below was
wrong by the time it mattered.** `GET /agent/broker/performance/
{artifact_id}` (and its `POST` counterpart) are real, implemented, and
tested (`vinu_agent/server/routes_broker.py`, `tests/test_routes_broker.py`
-- `TestBrokerOrderRoute::test_record_then_get_performance` et al.),
confirmed by reading the file directly, not by re-trusting this note. The
stale "does not exist yet" comment that used to sit in
`shadow_evaluator.py::_fetch_paper_sharpe` (matching the now-corrected
claim below) has been removed. `_fetch_paper_sharpe` now genuinely
succeeds against the real endpoint -- proven by
`test_shadow_fetch_reaches_the_real_endpoint_not_mocked` in
`vinu-live/tests/test_shadow_evaluator.py`, which runs the two services'
real code against each other (a real FastAPI TestClient standing in for
`agent-api`) rather than mocking `evaluator._http.get`.

**What's still true, confirmed dormant one way now (not three):**
- Grepped `ShadowEvaluator`/`shadow_evaluator` across every `vinu-*`
  service — referenced only inside its own file, plus one comment in
  `vinu_live/feedback_loop.py`. Nothing calls `evaluate_all()`: not
  `LiveScheduler.cycle()`, not `cli.py`, not any route in
  `vinu_live/server/app.py`. This part of the original finding still
  holds -- Phase 4 did not add a scheduler for this (out of Phase 4's own
  scope; see `01-plan.md`), it only fixed and tested the previously-wrong
  "endpoint doesn't exist" claim and closed the missing-test gap.

**This is a wiring gap, not a design gap, not a missing-endpoint gap
anymore.** The actionable next step (still out of scope for this doc, and
for Phase 4, to decide) is: something needs to call `ShadowEvaluator.
evaluate_all()` on a schedule — most naturally alongside `vinu-portfolio`'s
own scheduled pattern (see Stage 3 below, which solved exactly this kind
of gap once already). Until that happens, **an artifact promoted to
ACTIVE today has cleared Stage 1's statistical bar but has never been
checked against real paper-trading performance** -- the check itself now
genuinely works end to end when invoked, it's just never invoked
automatically yet.

### Stage 3 — Portfolio drawdown circuit breaker (real, running)

`vinu_portfolio/circuit_breakers.py::PortfolioDrawdownMonitor` +
`vinu_portfolio/drawdown_scheduler.py`. Unlike Stage 2, this one is
**confirmed genuinely running**, not just wired in code:
- `drawdown_scheduler.py`'s own docstring describes closing precisely the
  gap Stage 2 currently has: "the monitor and the halt transport... both
  existed and were tested, but nothing ever called `monitor.update()`
  with a real value. This is that caller." — direct precedent, in this
  same codebase, for exactly the fix Stage 2 needs.
- `monitor_main_loop()` polls `agent-api`'s `GET /broker/account` for
  live equity on `config.drawdown_monitor_interval_sec`, calls
  `monitor.update(equity)`, which halts trading via `POST /broker/halt`
  when drawdown breaches `config.drawdown_halt_threshold` (default -20%).
- `vinu-portfolio/entrypoint.sh` confirms this actually starts in the
  deployed container: `vinu-portfolio monitor &` runs in the background
  alongside `vinu-portfolio serve` in the foreground — both start
  together, every time the container starts. **This is the one stage
  confirmed live end-to-end: built, tested, wired, and started by
  default**, not just theoretically reachable.
- **Correction, found in a later full-codebase sweep:** the actual HTTP
  call this stage makes (`POST {agent_api_url}/broker/halt`) was, until
  fixed, missing `vinu-agent`'s own `route_prefix="agent"` — meaning the
  real call would have 404'd and the `except Exception` in
  `_halt_trading` would have logged an error and silently NOT halted
  trading, exactly the failure mode its own docstring warns about
  ("Trading is NOT halted — manual intervention required"). Fixed
  (now `POST .../agent/broker/halt`), along with the equivalent bug in
  `drawdown_scheduler.py`'s own `GET .../agent/broker/account` call — this
  stage's "confirmed live end-to-end" claim above is now actually true;
  it was not, before this fix, despite being correctly wired and scheduled.

### Stage 4 — Order-level enforcement (real, enforced, unbypassable by design)

`vinu_agent/server/routes_broker.py` (read in full — see Step 01
Findings §4). `/broker/halt`, `/broker/resume`, `/broker/status` sit on
top of `broker/kill_switch.py`. Critically, `/broker/order`'s own
docstring states it deliberately reuses the exact same `OrderGuard`
checks (kill switch, mandate limits, artifact gate, market hours) as the
LLM's own order-submission tool — so Stage 3's halt (or any other caller,
including a human operator) can't be bypassed by a second code path that
skips the guard. **This is the actual enforcement point** everything
above ultimately routes through.

**Correction, same sweep:** two of `OrderGuard`'s own checks —
`_check_active_artifact` (blocks orders for symbols without an ACTIVE,
promoted strategy) and `_check_portfolio_concentration` (blocks
over-concentrated buys) — call `vinu-research`'s `/artifacts` and
`vinu-portfolio`'s `/state` without their respective `/research` and
`/portfolio` prefixes. Both checks are deliberately designed to **fail
open** (allow the order, log a warning) if the downstream call throws —
so this bug meant both checks were silently always failing open,
regardless of the actual artifact/concentration state, rather than
enforcing anything. Fixed (`/research/artifacts`, `/portfolio/state`).
This was live-safety-relevant: the enforcement point itself (Stage 4) was
real and unbypassable, but two of the checks running *inside* it were
not actually checking anything.

### What this means in practice

- A strategy that is ACTIVE today reached that status through Stage 1
  only — a real statistical bar, but never checked against actual paper
  P&L (Stage 2 is dormant).
- Once trading, Stage 3's drawdown monitor is genuinely watching and will
  halt via Stage 4's kill switch on a -20% portfolio drawdown — this part
  of the safety net is real, not aspirational.
- There is currently no automated step between "passed the statistical
  research bar" and "trading live with real capital" that checks paper
  performance first. That gap is real, not hidden, and closing it is a
  wiring + testing task on already-existing code, not a design-and-build
  task from scratch.

### For Focus 3 (progressive daily portfolio, see the plan's Step 10)

Any daily allocation logic that decides how much capital to put behind a
strategy inherits everything above — an allocator has no way to know
whether a given ACTIVE strategy ever cleared Stage 2, because Stage 2
never ran. If Focus 3's allocation intelligence should weight
capital differently based on paper-trading confirmation, that requires
Stage 2 to actually run first; building around its absence (e.g. treating
every ACTIVE artifact as equally trusted) silently inherits this gap
rather than accounting for it.

### Daily risk budget — soft graduated response, between Stage 3 and per-position exits (Step 05, D5)

`vinu_portfolio/risk_budget.py::compute_risk_budget()`
(`GET /portfolio/risk/status`, CLI `vinu-portfolio risk-status`) adds a
softer, graduated layer that sits between the probabilistic per-position
exit (Step 03) and Stage 3's all-or-nothing -20% circuit breaker above.
Per symbol it computes a 3-tier response based on today's P&L as a
fraction of account equity:

| Tier | Threshold (default) | Effect |
|---|---|---|
| 0 (none) | above -1% | no change |
| `TIER_WARNING` (1) | ≤ -1% | flagged, no size change |
| `TIER_REDUCE` (2) | ≤ -2% | `suggested_size_multiplier` halved |
| `TIER_HALT` (3) | ≤ -3% | `suggested_size_multiplier` → 0.0 |

These are *suggestions* returned in the response (`suggested_size_multiplier`,
`halted`) — unlike Stage 3/4, this module does not itself call
`POST /broker/halt` or block an order. Nothing currently reads
`compute_risk_budget()`'s output to act on it automatically; it is a
decision-support signal for whatever places the next order (human or
agent), not an enforcement point. Treat it as informational until
something is wired to consume it the way Stage 4 consumes Stage 3.

**Regime tightening is a flat portfolio-wide multiplier, not the
tag-alignment formula from this step's research notes.** The step file's
research notes describe `alignment_score` (1.0 when regime matches a
strategy's tag, down to 0.3 when opposing) tightening each strategy's own
position limit and invalidation distance individually. What's actually
implemented, `REGIME_SIZING_MULTIPLIERS` (`{"bull": 1.0, "bear": 0.8,
"sideways": 0.9, "high_vol": 0.6}`), is simpler: one multiplier per
portfolio based only on the current regime label, applied uniformly to
every symbol's `regime_band_multiplier` — it does not look at any
strategy's tag alignment (`strategy-tags/tags.yaml`) at all. This is a
real, deliberate simplification for v1, not a bug — but it means "regime
tightening" here is coarser than what the research notes originally
scoped. Composing per-strategy tag alignment into this multiplier (like
`daily-allocation`'s `_REGIME_TO_TAGS` mapping does for allocation
weights) is future work, not done here.

**`DailyPositionTracker` does not accumulate across calls in production —
confirmed by tracing the only caller.** `compute_risk_status()`
(`service.py`) instantiates a fresh `DailyPositionTracker()` on every
single call before passing it into `compute_risk_budget()`. The tracker
class itself supports accumulating P&L across repeated
`record_daily_pnl()` calls through the day (and is unit-tested doing so),
but because a new, empty tracker is created per request, `daily_pnl` in
production is always just the latest snapshot of each position's
`unrealized_pl` from `/agent/broker/positions` for that one call — never
a running total built from polling `compute_risk_status()` repeatedly
through the day. Whether this matters depends on what `unrealized_pl`
itself represents (open-position mark-to-market vs. day's total P&L
including closed trades) — that wasn't traced further here. If a true
intraday accumulator is needed, `PortfolioService` needs to hold one
`DailyPositionTracker` instance across requests (e.g. as an instance
attribute, mirroring how `drawdown_scheduler.py` holds monitor state
across polls) instead of constructing one per call.
