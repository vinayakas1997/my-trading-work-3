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
   [REAL, ENFORCED]                 [BUILT, NEVER RUNS]          [REAL, RUNNING]               [REAL, ENFORCED]
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

**Confirmed dormant, three ways now:**
- Grepped `ShadowEvaluator`/`shadow_evaluator` across every `vinu-*`
  service — referenced only inside its own file, plus one comment in
  `vinu_live/feedback_loop.py`. Nothing calls `evaluate_all()`: not
  `LiveScheduler.cycle()`, not `cli.py`, not any route in
  `vinu_live/server/app.py`.
- No test file exists for it either (`vinu-live/tests/` has no
  `test_shadow_evaluator.py` equivalent) — unlike every other mechanism
- **`_fetch_paper_sharpe`'s target endpoint doesn't exist.** It calls
  `GET /agent/broker/performance/{artifact_id}` — grepped
  `vinu_agent/server/routes_broker.py` for "performance": zero matches.
  Even if something started calling `evaluate_all()` on a schedule today,
  this specific call would still 404 — the gap here is larger than
  "unwired," it's "the endpoint it needs was never built." (A missing-
  route-prefix sweep across the whole codebase, done alongside this
  finding, fixed the URL *shape* of this call — `/broker/performance/...`
  → `/agent/broker/performance/...` — but that doesn't change that the
  route itself is absent.)
  in this chain, it has never been exercised at all, not even in a test.

**This is a wiring gap, not a design gap.** The actionable next step (out
of scope for this doc to decide) is: something needs to call
`ShadowEvaluator.evaluate_all()` on a schedule — most naturally alongside
`vinu-portfolio`'s own scheduled pattern (see Stage 3 below, which solved
exactly this kind of gap once already) — and it needs test coverage
before being trusted. Until that happens, **an artifact promoted to
ACTIVE today has cleared Stage 1's statistical bar but has never been
checked against real paper-trading performance.**

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
