# Points 7 + 8 designed: the decision-to-execution handoff, and where all of this lives

**Status: design-only, nothing built.** Checked directly against real
code (2026-09-25).

## Part A — Point 7: the agent's decision has to survive contact with execution

### The real, confirmed gap it's landing on

`vinu-live/vinu_live/breaker/engine.py:139-163`'s `check_limits`:

```python
def check_limits(
    backend: BookBackend,
    prices: dict[str, float],
    portfolio_value: float,
    daily_realized_pnl: float,
    covariance_matrix: np.ndarray | None = None,
    cluster_map: dict[str, str] | None = None,
    limits: BreakerLimits | None = None,
    state: BreakerState | None = None,
) -> tuple[str, str | None]:   # (verdict, reason)
```

Real, working, checks daily-loss/VaR/position-count/cluster-exposure/
leverage (lines 157-163). Confirmed: only called from
`trade_plan/orchestrator.py`'s `_check_breaker` — **not** from
`LiveScheduler.cycle()` (`scheduler.py`), the path this new live-
decision loop would hand its "execute" decisions to. This is the parent
audit's item #24 finding #1, still real as of this check.

### The fix this design needs, concretely

When `live_decision_agent` (point 5) returns `decision: "execute"`,
that's not a broker order yet — it needs to become an instruction that
flows through `LiveScheduler`'s existing path (`_translator.translate()`
-> `_plan_execution()` -> `_execute_plan()`,
`scheduler.py:92-101`), with `check_limits()` inserted **before**
`_plan_execution` is called, gated on the same `BreakerState`/halt
mechanism `orchestrator.py` already uses correctly. This is exactly the
fix item #24 finding #1 already specified — this design doesn't change
that fix, it just makes concrete *why* it now blocks something new, not
just an existing gap: this whole live-decision loop's output would flow
straight past an unenforced risk limit if built before this fix lands.

### The second confirmed-still-open gap this also depends on

`SignalTranslator.translate()`
(`vinu-live/vinu_live/signal_translator.py:43-93`) builds one
`OrderInstruction` per `target_weights` entry with no groupby-symbol
step. If two strategies' `live_decision_agent` runs both reach
`execute` on the same symbol in opposite directions in the same cycle,
both orders still get generated independently — item #24 finding #2,
also still open, also not modified by this design, just newly relevant
to it.

### Where this decision loop's output actually enters `vinu-live`

Two options, not decided here:

1. **As a new `target_weights` contributor** — `live_decision_agent`'s
   "execute" decisions get translated into a weight delta and merged
   into whatever `LiveScheduler._fetch_portfolio()` already pulls from
   `vinu-portfolio`, so they flow through the *existing* translate/plan/
   execute path unchanged, gaining points 7's fixes "for free" once
   those fixes land.
2. **As a new, parallel signal-driven path**, closer to how
   `TradePlanOrchestrator` already works (individual entries/exits, its
   own gate stack) rather than the portfolio-rebalance path.

**Leaning toward option 1**: `TradePlanOrchestrator`'s path already has
its own risk-limit check wired correctly (per item #24's own "confirmed
genuinely good" section) — building a *third* execution path here would
mean a *third* place same-symbol-netting and risk-limit-checking has to
be independently re-verified, repeating exactly the "N independent
components, same missing wiring" pattern the parent audit's item #21
already found 3-4 times over. Funneling through the existing
`LiveScheduler` path means this design's only real new execution-side
work is the two fixes item #24 already specified — not a new gate stack.
Not finalized; flagged as the recommended default, not a decision.

## Part B — Point 8: where the poller/state-tracker/detector/agent actually live

### The real precedent already on record

`01-planning.md` Decision 10 already drew this exact line, for a
narrower case (the historical backfill angle vs. a hypothetical live
detector): `vinu-initial-analysis` is **backfill-rhythm** — triggered by
ticker discovery, runs over `[from_ts, to_ts]` historical ranges,
tracked via `RunLog.analysis_from/until`. It is explicitly *not* meant
to also host something running "every cycle, on open positions" — a
different rhythm entirely. Decision 10's own words: this doesn't replace
"the still-unbuilt LIVE detector `vinu-live` would need."

### Applying that same reasoning to all four new pieces (points 2-5)

- **The poller (point 2)** — real-time, candle-close-driven. Same
  `while True: cycle(); sleep()` shape already used by `vinu-live`'s
  existing workers (`scheduler.py`, `feedback_loop.py`,
  `shadow_evaluator.py` — confirmed real precedent, not assumed).
  Belongs in `vinu-live`.
- **The state tracker (point 4)** — needs to be checked and updated
  every poll cycle, in lockstep with the poller. Same home.
- **The live detector (point 3)** — needs fresh bars every poll cycle;
  no backfill-style date-range bookkeeping applies to it at all. Same
  home.
- **The deciding agent (point 5)** — architecturally different: it's an
  LLM-tool-calling agent, and every other agent in this codebase lives
  under `vinu-agent/teams/`, not inside `vinu-live` (`vinu-live` has no
  `teams/` directory or agent-framework dependency today — confirmed by
  directory listing). This one is genuinely split: the *trigger* (poller
  reaching `ready_to_execute`) lives in `vinu-live`, but the *agent
  itself* lives in `vinu-agent`, called the same way `vinu-live` already
  calls into other services over HTTP (e.g. `feedback_loop.py`'s
  existing `_record_calibration_outcome` POST to `vinu-research`, cited
  in `../../01-planning.md` Decision 8 as the established wiring
  precedent for exactly this kind of cross-service call).

### The recommended shape, stated plainly

```
vinu-live/  (new module, e.g. vinu_live/live_decision/)
  poller.py          # point 2
  state_tracker.py   # point 4
  detector.py         # point 3 (calls vinu_tools directly + vinu-stock-price)
  -- on reaching ready_to_execute --
  HTTP call to vinu-agent's live_decision_agent (point 5)
  -- decision returned --
  merged into LiveScheduler's existing translate/plan/execute path (point 7, option 1)
```

**Resolved (2026-09-26), built and tested**: `vinu-agent` exposes
`POST /agent/live-decision/run` (`server/routes_live_decision.py`),
reusing the already-running `AgentService`'s own `SessionService` rather
than a separate invocation path — same `_get_service` module-level
wiring every other route in that directory already uses. The route
calls a new `SessionService.run_team_once(team_name, task)` method
(`session/service.py`), which mirrors `_run_with_agent`'s own real
`build_registry()`-then-`TeamManager(...)` construction (the exact
pattern `submit_thesis_tool.py`'s `_run_team` already uses, confirmed by
reading it directly before writing this), just without the
chat-session-specific machinery (`WorkflowTracker`, `FreshnessChecker`,
`GroundTruthInjector`, `ResearchDigestReader`, debrief detection) that
doesn't apply to a one-off headless run. `vinu-live`'s poller
(`live_decision/poller.py::_trigger_live_decision`) calls it exactly
once per (ticker, strategy) pair the instant it **freshly** reaches
`ready_to_execute` — not every cycle it sits there — and resolves the
trigger's lifecycle (`state_tracker.mark_executed`, now accepting a
`reason` for EXECUTE vs. SKIP) once a real decision comes back. A failed
call is logged, not raised, and leaves the pair in `ready_to_execute` to
retry next cycle rather than losing the trigger. The latency question
this note originally raised wasn't resolved by design — it's resolved by
observation: `run_team_once` is genuinely cheap to construct per call
(confirmed directly: `build_registry()` reuses the `SessionService`'s
already-open shared stores, it doesn't stand up a second LLM client or
duplicate any store), so the real latency cost is just the LLM call
itself, same as every other agent-based decision in this codebase.

## What both parts leave open

- ~~Exact HTTP contract between the new `vinu-live` module and
  `live_decision_agent`~~ — resolved and built, see Part B above
  (`POST /agent/live-decision/run`, `{ticker, strategy_id, trigger_id}`
  request, `{status, decision, precondition_held, reasoning, content}`
  response).
- ~~Whether option 1 or option 2 (Part A) is actually chosen~~ —
  **Resolved (2026-09-26), built and tested: option 1.** `live_decisions`
  gained an `applied`/`applied_at` pair (storage.py SCHEMA_VERSION 2,
  MIGRATIONS for existing databases). `LiveScheduler` opens a second
  `LiveDecisionBackend` on the same on-disk file the poller already
  writes (same safe-shared-file reasoning already applied to `self._book`).
  Every `cycle()` now calls `_fetch_live_decision_weights()` first, which
  reads `list_unapplied_executes()`, sizes each one via a new
  `StrategyConfig.live_decision_position_size` field (vinu-strategy),
  and folds the result straight into the same `target_weights` list the
  normal portfolio-rebalance path already uses -- gaining item #24's
  risk-limit check (`_check_breaker`) and same-symbol netting
  (`SignalTranslator._net_by_symbol`) for free, exactly as this doc's
  "leaning toward option 1" reasoning predicted, not a second gate stack.
  `live_decision_position_size` deliberately defaults to `0.0`
  ("unsized") rather than any guessed fraction -- a must-condition-only
  strategy has no other sizing mechanism defined anywhere. An unsized
  EXECUTE is marked `applied` (real, final information: not configured
  yet) and logged loudly rather than silently dropped or endlessly
  retried; a strategy-config *fetch failure* is left unapplied and
  retried next cycle, since that's transient, not a real "not sized" fact.
- Latency budget for the whole chain (poll -> detect -> state-check ->
  agent call -> execution handoff) relative to the shortest strategy
  timeframe in use — not analyzed here.
