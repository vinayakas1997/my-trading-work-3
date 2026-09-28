# Implementation status — what's actually been built, kept current

**Purpose**: a single place to check, at any point, what's real vs. what's
still just design — for this `reverse-engineering/` folder's 9 points
specifically. Updated every time something actually gets designed in
detail or built, not written once and left stale. Mirrors the same
honest-status convention the rest of this folder series already uses
(e.g. `../../02-implementation-status.md` at the top level).

**Rule for keeping this honest**: a point only moves to "designed" once
its table schema / API-call shape is actually written down (not just
discussed), and only moves to "built" once real code exists and runs —
matching the same bar `01-planning.md`'s own decisions use ("nothing
implemented" stated plainly until it is).

## Status table

| # | Point | Design status | Build status |
|---|-------|---------------|--------------|
| 1 | Strategy → ticker → polling cadence | Already exists (`StrategyConfig.schedule`) | Already exists |
| 2 | Candle-close poller | Designed — see `03-poller-and-state-schema.md` (Part A) | **Built** — `vinu-live/vinu_live/live_decision/poller.py` (`CandleClosePoller`), CLI: `live-decision-cycle`/`live-decision-worker` |
| 3 | Live indicator computation ("live detector") | Designed — see `04-live-detector-schema.md` | **Built** — `vinu-live/vinu_live/live_decision/detector.py` (`compute_live_snapshot`), `bars_client.py` |
| 4 | Stage/state tracker per (ticker, strategy) | Designed — see `03-poller-and-state-schema.md` (Part B) | **Built** — `vinu-live/vinu_live/live_decision/state_tracker.py`, `storage.py`, `schema.py` |
| 5 | The querying/deciding agent (Layer 5) | Designed — see `05-deciding-agent-and-precondition-tracking.md` | **Built** — tool (`get_live_decision_context`), agent (`live_decision_agent`, team `live_decision`), the trigger route (`POST /agent/live-decision/run`, `session/service.py::run_team_once`), and the poller wiring that calls it exactly once per fresh `ready_to_execute` and resolves the trigger's lifecycle on a real decision. Full chain built, tested, and passing |
| 6 | Precondition `defined`/`tested` tracking | Designed — see `05-deciding-agent-and-precondition-tracking.md` | **Fully built** — schema fields on `StrategyConfig` (unchanged from before), plus the write-back path: `vinu-strategy/vinu_strategy/storage/precondition_state.py` (`PreconditionStateStore`, a separate SQLite table, deliberately not the strategy's own YAML file), `POST /strategy/strategies/{name}/precondition-check` (called by `vinu-live/vinu_live/live_decision/poller.py::_record_precondition_check` on every real EXECUTE/SKIP verdict), overlaid onto `GET /strategy/strategies/{name}`'s `precondition` dict at read time |
| 7 | Decision → execution handoff (item #24 fixes) | Designed — see `06-execution-handoff-and-architecture.md` | **Fully built, all 3 item #24 findings closed** — `vinu-live/vinu_live/scheduler.py` (`_check_breaker`/`_engage_real_halt`, finding #1; `_handle_reconciliation_drift`/`_notify_target_weight_drift`, finding #3; `_fetch_live_decision_weights`, option 1's handoff) and `vinu_live/signal_translator.py` (`_net_by_symbol`, finding #2). A live EXECUTE decision now folds into `LiveScheduler`'s own `target_weights` flow, sized by `StrategyConfig.live_decision_position_size` (vinu-strategy), and goes through the same risk-limit check, netting, and drift-alerting as every other weight |
| 8 | Architectural home for poller/agent | Designed and **built as designed** — poller/detector/tracker live in `vinu-live/vinu_live/live_decision/`, the agent lives in `vinu-agent/teams/live_decision/`, connected by `POST /agent/live-decision/run` | Built — see point 5 |
| 9 | Layer 4 probabilistic/bucket table | Deliberately deferred — see `07-bucket-table-deferred.md` | Not built |

## Log

**2026-09-25** — Folder created (`00-overview.md`,
`01-live-decision-loop-open-points.md`). All 9 points captured and
cross-referenced against the parent audit series. Nothing designed in
schema/API detail yet, nothing built. This file created to track
progress from here forward.

**2026-09-25** — Points 2 (candle-close poller) and 4 (stage/state
tracker) designed in full schema/loop detail: `live_poll_cursor`,
`strategy_stage_state`, `strategy_stage_transitions` tables, the poll
loop, and the per-candle-close evaluation logic. See
`03-poller-and-state-schema.md`. Nothing built yet — design only. Chosen
first because points 3/5/6 all depend on this foundation existing.

**2026-09-25** — Points 3, 5, 6, 7, 8, and 9 all designed in the same
pass, checked directly against real code (`vinu-tools`, `vinu-stock-
price`, `vinu-agent`'s `BaseTool`/`AGENT.md` pattern, `vinu-live`'s
`breaker/engine.py::check_limits`, `vinu-strategy`'s real
`StrategyConfig` schema). See `04-live-detector-schema.md`,
`05-deciding-agent-and-precondition-tracking.md`,
`06-execution-handoff-and-architecture.md`, `07-bucket-table-
deferred.md`. Point 9 deliberately left undesigned in detail (real
reason given, not skipped). **All 9 points are now designed** (or
deliberately deferred, in point 9's case) — nothing built yet. Next step
is implementation, in dependency order: points 2+4 first (the
foundation), per the plan agreed before this pass started.

**2026-09-25** — Points 2, 3, and 4 built for real, checked directly
against the live codebase (not guessed) before writing:

- `vinu-strategy`: `StrategyConfig` gained `must_conditions`/
  `confirmation_conditions`/`grace_window_bars` fields (`models/
  strategy.py`); `Condition.source` gained a `"live_indicators"` option
  (`models/rules.py`); `StrategyService.resolve_universe()` and
  `StrategyAPI.get_strategy()` now expose the strategy's resolved
  ticker universe + the new fields over HTTP (`GET /strategy/
  strategies/{name}`). All 78 existing `vinu-strategy` tests still pass.
- `vinu-live`, new module `vinu_live/live_decision/`: `schema.py`
  (dataclasses), `storage.py` (`LiveDecisionBackend`, the same
  `SQLiteBackend` pattern `book/positions.py` already uses),
  `conditions.py` (must-condition/confirmation-condition evaluator,
  reusing `vinu-strategy`'s own `{source, key, operator, value}`
  vocabulary rather than a new DSL), `detector.py` (point 3 — calls
  `vinu_tools.compute.registry.apply_indicators`, the "blessed" entry
  point item #20.6 in the parent audit flagged as underused, plus the
  small set of derived ratios `signal_evidence/compute.py` also
  computes), `bars_client.py` (shared live-bar fetch), `poller.py`
  (point 2, `CandleClosePoller`), wired into `cli.py`
  (`live-decision-cycle`/`live-decision-worker` commands) and
  `pyproject.toml` (`vinu-live-decision-worker` console script).
- **41 new tests**, all passing: `test_live_decision_conditions.py` (6),
  `test_live_decision_storage.py` (5), `test_live_decision_state_
  tracker.py` (9), `test_live_decision_detector.py` (8),
  `test_live_decision_poller.py` (5) — plus confirmed zero regressions:
  full `vinu-strategy` suite (78 passed) and full `vinu-live` suite (475
  passed; 3 pre-existing, unrelated errors from a missing `vinu_agent`
  module in this local environment, not caused by this change).
- **Not yet done**: nothing calls `live-decision-worker` from any real
  deployment config (docker-compose, etc.) — it exists and is tested in
  isolation, not yet wired into the running system. Point 5 (the
  deciding agent that actually consumes a `ready_to_execute` state) is
  still not built, so today a real must-condition firing would sit in
  `ready_to_execute` with nothing consuming it — expected, since point 5
  is next, not a bug in what's built so far.

**2026-09-25** — Point 5's tool + agent built, and point 6's remaining
schema field (`precondition`) added:

- `vinu-live`: closed an open design question from `04-live-detector-
  schema.md` ("leaning toward persist it, not decided") by actually
  persisting point 3's live snapshot on `strategy_stage_state.
  last_snapshot`, threaded through every `state_tracker.py` transition.
  New route `GET /live/decision-context/{ticker}/{strategy_id}`
  (`server/app.py`) exposes stage + snapshot for point 5 to read.
- `vinu-strategy`: added the `precondition: {description, defined}`
  field to `StrategyConfig` (`tested` deliberately NOT stored — no
  write-back path decided yet, documented inline rather than faked).
- `vinu-agent`: new tool `get_live_decision_context`
  (`vinu_agent/tools/get_live_decision_context_tool.py`) — composes
  vinu-live's decision-context route, vinu-strategy's strategy config,
  and the existing `get_signal_evidence` tool (reused, not
  reimplemented) into one call. New team `teams/live_decision/` with
  agent `live_decision_agent` — modeled directly on `thesis_intake`/
  `theory_reviewer`'s real pattern, including the same "no execution
  tool in the list, enforced by omission" safety posture. **Verified**
  (not just written): both `load_team_spec`/`load_agent_spec` parse it
  correctly, and every tool it declares resolves against the real
  `ToolRegistry` with zero missing.
- **Deliberately stopped here, not a gap being hidden**: the piece that
  would make this fully live end-to-end — something that automatically
  calls `live_decision_agent`'s team the instant vinu-live's state
  tracker reaches `ready_to_execute` — is not built. Checked directly
  (`submit_thesis_tool.py`'s real pattern): triggering a team requires
  `TeamManager(team_dir, full_registry=..., llm=..., run_store=...,
  ...)`, a shared dependency-injection bundle assembled centrally in
  `AgentService`/tool-registry construction, not something safe to
  hand-assemble inside a fresh, isolated tool without directly reading
  how that central wiring works first. A mistake there risks breaking
  the *existing* working `thesis_intake`/`submit_thesis` path too, not
  just this new one. Matches point 8's own design doc, which already
  flagged this exact HTTP-contract question as "not decided."
- **11 new tests**, all passing: `test_live_decision_state_tracker.py`
  gained 1 (`last_snapshot` persistence), `test_decision_context_route.py`
  (2, new), `test_get_live_decision_context_tool.py` (4, new in
  vinu-agent). Confirmed zero regressions: full `vinu-strategy` (78
  passed), full `vinu-live` `live_decision`-related suite, and full
  `vinu-agent` suite (1335 passed, 16 failed + 2 errors — all pre-
  existing, confirmed by `git status` showing zero modifications to any
  file those failures touch; this session only added 2 new files there).

**2026-09-26** — Point 7 built: the two item #24 CRITICAL fixes, real code:

- `vinu-live/vinu_live/scheduler.py`: `LiveScheduler` now constructs its
  own `BookBackend` (same shared on-disk path — `trade_plan_book.db` —
  `orchestrator.py`/`feedback_loop.py` already use) and `BreakerState`,
  and calls `check_limits()` before any order is planned/submitted
  (finding #1: this loop used to never call it at all). Modeled directly
  on `orchestrator.py`'s own real `_check_breaker`/`_engage_real_halt`
  methods — same shape, same real cross-process kill-switch POST on a
  fresh HALT, not a second, drifting implementation. Deliberately scoped:
  passes `covariance_matrix=None` (the real `_compute_covariance` is
  tightly coupled to the orchestrator's own caching, not yet extracted
  into something both paths share) — `check_limits()` already treats
  `None` as "skip the aggregate-VaR check only," every other check
  (daily loss, position count, cluster exposure, leverage) still runs in
  full. A real, named, scoped gap, not hidden.
- `vinu-live/vinu_live/signal_translator.py`: `SignalTranslator.translate()`
  now nets `target_weights` entries by symbol (`_net_by_symbol`) before
  building instructions (finding #2: two strategies' opposite-direction
  entries used to each fire their own order against the same unchanged
  position snapshot — a real buy-then-sell whipsaw). Chosen as the
  provisional default per item #23's own framing (net vs. keep-separate
  vs. block is "the user's call, not a default to assume") — netting was
  picked because it needs no new downstream machinery and is a strict
  improvement over the confirmed bug either way, documented as
  provisional in the docstring, not a claim the policy question is
  closed. Logs a warning when netted contributions have opposite signs,
  for visibility.
- **Not done**: point 5's decision output doesn't feed into this path
  yet (design doc's "option 1" — merging a `live_decision_agent`
  recommendation into `LiveScheduler`'s existing `target_weights` flow)
  — these two fixes stand alone, closing the two CRITICAL item #24 gaps
  on their own terms, not yet wired to the new live-decision loop.
- **8 new tests**, all passing: `test_scheduler_breaker.py` (4, new —
  verifies the wiring, not `check_limits`' own math, which
  `test_breaker.py` already covers) and `TestSameSymbolNetting` in
  `test_signal_translator.py` (4, new). Confirmed zero regressions: full
  `vinu-live` suite, 486 passed (up from 478 before this round, exactly
  +8), same 3 pre-existing unrelated errors as every prior run.

**2026-09-26** — Point 5's automatic trigger built (closing the last
open question in point 8), plus point 8 marked built-as-designed:

- `vinu-agent/vinu_agent/session/service.py`: new
  `SessionService.run_team_once(team_name, task, tag="")` — checked
  `submit_thesis_tool.py`'s real `_run_team` pattern directly first
  (the only existing precedent for "run a team outside a normal
  request"), then mirrored its exact `build_registry()` +
  `TeamManager(...)` construction, reusing this service's own
  already-open shared stores rather than a second set. A first attempt
  used the wrong relative-import depth (`from .tools import
  build_registry` inside `session/service.py`, which resolves to a
  nonexistent `vinu_agent.session.tools`) — caught immediately by the
  new tests, fixed to `from ..tools import build_registry`.
- `vinu-agent/vinu_agent/server/routes_live_decision.py` (new) +
  `server/app.py` wiring: `POST /agent/live-decision/run`, same
  `_get_service` module-level pattern every other route file already
  uses. Confirmed via `create_app()`'s own OpenAPI schema that the route
  actually registers, not just that the file has no syntax errors.
- `vinu-live/vinu_live/live_decision/poller.py`:
  `_trigger_live_decision` calls the new route exactly once per
  (ticker, strategy) pair the instant it **freshly** reaches
  `ready_to_execute` (compares stage before/after
  `evaluate_candle_close`, not "every cycle it happens to still be
  there"). A failed call is logged, not raised, and leaves the pair in
  `ready_to_execute` to retry next cycle. `state_tracker.mark_executed`
  gained a `reason` parameter so both EXECUTE and SKIP decisions
  correctly resolve the trigger's lifecycle (previously hardcoded to
  `"agent_executed"` only).
- **12 new tests**, all passing: `test_session_service_run_team_once.py`
  (2, new), `test_routes_live_decision.py` (4, new),
  `TestLiveDecisionTrigger` in `test_live_decision_poller.py` (3, new).
  Confirmed zero regressions: full `vinu-live` suite (489 passed, up
  from 486, exactly +3 — the poller-side tests only; the
  vinu-agent-side 6 tests are counted in that suite's own run) and full
  `vinu-agent` suite (1341 passed, up from 1335, exactly +6; same 16
  failures + 2 errors as every prior run, all pre-existing).
- **What's still open, honestly**: point 7's fixes and point 5's
  decision output are still two separate paths — a live EXECUTE
  decision resolves the state tracker's lifecycle but does not yet
  cause `LiveScheduler` to actually plan/submit a real order (design
  doc's "option 1," still not built). The live decision loop can now
  run end-to-end from candle-close through to a recorded EXECUTE/SKIP
  decision — it just doesn't place a trade yet.

**2026-09-26** — Closed a real gap found mid-session, not in the
original 9 points but the same recurring pattern as item #21.3
("compute a real reason, then discard it"): `live_decision_agent`'s
actual verdict — a genuine, evidence-grounded LLM answer — was being
computed, returned over HTTP, and then only logged at INFO level.
Nothing durable kept it. Fixed with a proper record-and-access pair,
not just a patch:

- `vinu-live/vinu_live/live_decision/schema.py` + `storage.py`: new
  `LiveDecisionRecord` dataclass and `live_decisions` table (append-only,
  same pattern `strategy_stage_transitions` already uses) —
  `record_live_decision`/`list_live_decisions`. Records EXECUTE, SKIP,
  EXTEND_GRACE_WINDOW, and even a failed HTTP call (`decision="error"`)
  — every real outcome, not just the successful ones.
- `vinu-live/vinu_live/live_decision/poller.py::_trigger_live_decision`:
  now writes a record for every branch, before deciding what to log/do
  with the result — recording happens even when the decision comes back
  unrecognized or the call fails outright.
- `vinu-live/vinu_live/server/app.py`: new
  `GET /live/decisions/{ticker}/{strategy_id}` — the "accessing" half,
  same honest-raw-rows posture `get_signal_evidence` already commits to.
- `vinu-agent`'s `get_live_decision_context` tool now also fetches this
  history (`past_live_decisions` field) and composes it into the same
  one-call context `live_decision_agent` already reads — closing the
  loop so past decisions become real context for future ones, not just
  an audit trail nobody reads. The agent's `prompt.md` was updated to
  actually use this field (check for a recent SKIP with a still-valid
  reason before flip-flopping without cause).
- **7 new tests**, all passing: 3 in `test_live_decision_storage.py`,
  2 in `test_decision_context_route.py`, 2 in
  `test_live_decision_poller.py` (the recording-verification tests,
  distinct from the earlier trigger-wiring tests). Plus
  `test_get_live_decision_context_tool.py` updated (not net-new count)
  to cover the fourth composed source. Confirmed zero regressions: full
  `vinu-live` suite (496 passed, up from 489, exactly +7) and full
  `vinu-agent` suite (1341 passed, unchanged — no new vinu-agent test
  count since the tool test was edited in place, not added to; same 16
  failures + 2 errors as every prior run, all pre-existing).

**2026-09-26** — Point 7's last open piece built: option 1, the actual
decision → order handoff (previously the two item #24 fixes stood alone
with nothing feeding into them):

- `vinu-live/vinu_live/live_decision/schema.py` + `storage.py`:
  `LiveDecisionRecord` gained `applied`/`applied_at` (SCHEMA_VERSION 2,
  `ALTER TABLE` migrations for databases from before this fix). New
  `list_unapplied_executes()`/`mark_decision_applied()` — the scheduler's
  own queue of EXECUTE verdicts still needing to become a real order.
- `vinu-strategy`: `StrategyConfig` gained `live_decision_position_size`
  (default `0.0`, "unsized") — the only new sizing concept this required.
  No default fraction was invented: a must-condition-only strategy has no
  other sizing mechanism anywhere (the selection/allocation/timing/risk
  pipeline is a separate mechanism from must_conditions), so guessing one
  here would be fabricating real position sizing, not a safe fallback.
  Exposed via `GET /strategy/strategies/{name}`.
- `vinu-live/vinu_live/scheduler.py`: `LiveScheduler` opens a second
  `LiveDecisionBackend` on the same on-disk file the poller already
  writes (same safe-shared-file reasoning as `self._book`). New
  `_fetch_live_decision_weights()` runs first in every `cycle()`, reads
  unapplied EXECUTEs, sizes each via the strategy's
  `live_decision_position_size`, and folds the result into the same
  `target_weights` list the portfolio-rebalance path already uses —
  gaining `_check_breaker` and `_net_by_symbol` "for free," exactly the
  design doc's recommended default, not a second gate stack. An unsized
  EXECUTE is marked applied and logged loudly (real, final information —
  not configured yet), never silently dropped or retried forever; a
  strategy-config *fetch failure* is left unapplied and retried next
  cycle, since that's transient, not a real "not sized" fact.
- **14 new tests**, all passing: 4 in `test_live_decision_storage.py`
  (`TestUnappliedExecutes`), 5 in new
  `test_scheduler_live_decision_weights.py`, 5 in new
  `test_live_decision_position_size.py` (vinu-strategy). Confirmed zero
  regressions: full `vinu-live` suite (505 passed, up from 496, exactly
  +9; same 3 pre-existing unrelated errors as every prior run) and full
  `vinu-strategy` suite (83 passed, up from 78, exactly +5).
- **What point 7 leaves open, honestly**: `precondition.tested`'s
  write-back path (point 6) is still undecided, unchanged by this. No
  exit mechanism exists for a position a live EXECUTE opened — once
  applied, the position is held like any other until something else
  (not yet built) decides to close it; reconciliation only reports drift
  on it, never auto-corrects. Not addressed here — a real, separate
  open question, not silently assumed away.

**2026-09-26** — Closed the last "not yet done" flagged in this file:
`live-decision-worker` is now started in the real deployment, not just
tested in isolation. Same real, recurring shape this codebase's own
`entrypoint.sh` already documents three times over (trade-plan-worker,
feedback-worker, shadow-worker, trade-plan-approval-worker: "real,
complete, nothing ever invoked it"):

- `vinu-live/entrypoint.sh`: added `vinu-live live-decision-worker &`,
  same background-loop pattern as every other worker already listed
  there, foreground `serve` still owns the container's lifecycle.
- `docker-compose.yml`: `live-api`'s `depends_on` gained `quant-core-api`
  (the real host of vinu-strategy's `/strategy/strategies` routes, per
  `.env-example`'s own `VINU_STRATEGY_API_URL=http://quant-core-api:8084`)
  -- a real, new dependency this session's work introduced (confirmed via
  `git diff`: `strategy_api_url` did not exist on `LiveConfig` before this
  folder's work started), not a pre-existing gap. Without it, the
  live-decision poller and scheduler's live-decision-weight fetch would
  both race quant-core-api's own startup on a fresh `docker compose up`.
- No test changes needed (deployment config, not application code) --
  verified both files parse (`yaml.safe_load`, `bash -n`) and confirmed
  zero regressions: full `vinu-live` suite still 505 passed, same 3
  pre-existing unrelated errors as every prior run in this session.

**2026-09-26** — Item #24's last open finding closed: finding #3
(reconciliation drift computed but never inspected/alerted on
`LiveScheduler`'s main path). All three of item #24's findings are now
fixed.

- `vinu-agent/vinu_agent/server/routes_notify.py`: `ReconciliationDriftRequest`
  gained `expected_qty`/`actual_qty`/`drift_pct` alongside the existing
  `book_qty`/`broker_qty` — a genuinely different comparison
  (target-weight vs. broker-position, not book-ledger vs. broker) reusing
  the same route with a new `action="target_weight_drift"`, not a second
  route, same "shared infra, not N one-offs" reasoning already applied
  throughout this series.
- `vinu-live/vinu_live/scheduler.py`: new `_handle_reconciliation_drift`/
  `_notify_target_weight_drift`, called at the end of every `cycle()`.
  **Deliberately not "alert on any drift"**: this reconciliation compares
  a target that just changed *this* cycle against positions fetched
  *before* this same cycle's own orders were submitted, so some drift on
  any cycle where the target moved at all is the expected gap those
  orders are already closing, not an anomaly — alerting on that would be
  pure noise on every rebalance. Instead, same fix shape item #23 finding
  #4 already uses for `consecutive_unavailable_count`: tracks a
  per-symbol consecutive-cycle drift streak, only notifies once a streak
  crosses `RECON_DRIFT_ALERT_CYCLES` (3, a guessed starting constant,
  same posture and same number as that finding's own), edge-triggered so
  it notifies once per newly-persistent streak, same shape as
  `orchestrator.py`'s own `_recon_drift_notified`.
- **11 new tests**, all passing: 1 in `test_routes_notify.py`
  (`test_reconciliation_drift_describes_target_weight_drift`), 6 in new
  `test_scheduler_reconciliation_drift.py` (`_handle_reconciliation_drift`
  tested directly against constructed `ReconciliationReport`s, same "test
  the wiring, not re-derive full system dynamics" posture
  `test_scheduler_breaker.py` already uses for `check_limits`, plus one
  end-to-end check that `cycle()` actually calls it). Confirmed zero
  regressions: full `vinu-live` suite (511 passed, up from 505, exactly
  +6; same 3 pre-existing unrelated errors as every prior run) and full
  `vinu-agent` suite (1342 passed, up from 1341, exactly +1 -- the new
  `test_reconciliation_drift_describes_target_weight_drift`; same 16
  failures + 2 errors as every prior run, all pre-existing).

**2026-09-28** — The exit-mechanism gap this file's point 7 log left open
("no exit mechanism exists for a position a live EXECUTE opened") closed,
after `04-synthesis-built-vs-missing-2026-09-28.md` (in the parent
folder) traced the code and found the gap was actually worse than
"missing": `LiveScheduler._fetch_live_decision_weights` only ever folded
an EXECUTE into `target_weights` for the single cycle it was applied,
and `SignalTranslator.translate()`'s own documented rule ("held but
absent from `target_weights` -> target 0.0") meant the position was
liable to be force-closed the very next cycle, not held indefinitely as
this file previously stated. No test had ever exercised a second cycle,
so this had never actually fired in practice, but was live risk.

- `vinu-live/vinu_live/live_decision/schema.py` + `storage.py`: new
  `LiveDecisionOpenPosition` dataclass and `live_decision_open_positions`
  table (SCHEMA_VERSION 3) -- `open_position`/`list_open_positions`/
  `mark_position_reviewed`/`close_position`. This table, not the
  one-time `applied` flag, is now the source of truth `LiveScheduler`
  reads every cycle.
- `vinu-live/vinu_live/scheduler.py`: `_fetch_live_decision_weights` now
  does two things instead of one -- converts a fresh unapplied EXECUTE
  into a real open-position row (unchanged sizing/unsized semantics),
  then re-emits a `target_weights` entry for **every** currently open
  position on **every** cycle, using the position's own stored size
  (not a fresh strategy-config fetch, so a later config edit doesn't
  retroactively resize an already-open position). This is the actual bug
  fix.
- `vinu-live/vinu_live/live_decision/poller.py`: new
  `_review_open_positions`/`_trigger_position_review`, called at the end
  of every `cycle()`. On a bar-count cadence
  (`LiveConfig.live_decision_position_review_cadence_bars`, default 5,
  a guessed starting constant same posture as `grace_window_bars`),
  re-invokes the same `/agent/live-decision/run` route with `mode:
  "review"` for each open position. HOLD keeps it open; EXIT calls
  `close_position`, after which the *next* scheduler cycle naturally
  omits its weight and the existing "not targeted -> close" rule sells
  it -- no new sell logic was written, reusing that mechanism was the
  point. Every real outcome (HOLD, EXIT, a failed call, an unrecognized
  answer) is durably recorded via the same `LiveDecisionRecord`/
  `record_live_decision` this file's point 5 already established, under
  a synthetic `pos_<id>` trigger_id. Only HOLD/EXIT advance
  `last_reviewed_bar_ts`; a failed call retries next cycle immediately
  rather than waiting a full cadence again.
- `vinu-agent`: `routes_live_decision.py`'s `LiveDecisionRequest` gained
  `mode`/`position_context`, folded into the task text as `Mode:
  POSITION_REVIEW` plus the position's opened_at/opened_bar_ts/
  position_size. `live_decision_agent`'s `prompt.md` and the team's
  `manager_prompt.md` gained a full "review mode" section -- same team,
  same tools (`get_live_decision_context`/`get_signal_evidence`), same
  "cannot place an order" posture, only the decision vocabulary
  (HOLD/EXIT) and the question being asked differ. Deliberately **not**
  a new team/tool: reuses the existing entry-mode machinery per this
  series' own "reduce, don't rebuild" precedent (point 5's own citation
  of `05-deciding-agent-and-precondition-tracking.md`).
- Deliberately **not** built: REDUCE/ADD (partial-close/add-to-position
  sizing has no mechanism anywhere in this codebase yet -- would be
  fabricating new position-sizing logic, not reusing an existing one);
  a real unrealized-P&L or confidence number to hand the reviewing agent
  (the same Phase 3/Layer 4 bucket-table gap point 5 already documents,
  unchanged by this fix).
- **43 new tests**, all passing: 5 in `test_live_decision_storage.py`
  (`TestLiveDecisionOpenPositions`), 2 in
  `test_scheduler_live_decision_weights.py` (one inline assertion added
  to the existing sized-EXECUTE test, one new
  `TestOpenPositionReEmittedEveryCycle` proving the cross-cycle fix
  directly), 7 in `test_live_decision_poller.py`'s new
  `TestPositionReview`, 2 in `test_routes_live_decision.py`'s new
  `TestReviewMode`. Confirmed zero regressions: full `vinu-live` suite
  (540 passed, 0 errors -- previously-noted pre-existing environment
  errors from a missing `vinu_agent` install no longer reproduce in this
  environment, confirmed not caused by this change since none of this
  session's files touch that import path) and full `vinu-agent` suite
  (1459 passed, 4 skipped, 0 failed).

**2026-09-28** — Point 6's last open piece built: the `precondition.
tested`/`precondition_held` write-back path, previously left "no store/
API decided."

- **The one real design decision this needed, made explicitly**: NOT
  written back into the strategy's own YAML file
  (`StrategyRegistry.load_all()`) -- that file is a human-authored,
  declarative source of truth reloaded on its own schedule; a live
  process writing into it would blur config (human-owned) with derived
  runtime state (system-owned), the same split `MetaStorage`/
  `WeightStorage` already draw for every other kind of per-strategy
  state in `vinu-strategy`. Instead: a new, separate
  `vinu_strategy/storage/precondition_state.py`
  (`PreconditionStateStore`, one row per strategy_name, upserted not
  appended -- the append-only audit trail of every individual check
  already lives in vinu-live's own `live_decisions` table), overlaid
  onto the YAML-sourced `precondition` dict at read time
  (`StrategyAPI.get_strategy()`/`_precondition_dict()`), never mutating
  the file itself.
- New `POST /strategy/strategies/{name}/precondition-check`
  (`routes_read.py`) — 404s for an unknown strategy name (typo
  protection), otherwise records the check and returns the updated
  overlay.
- `vinu-live/vinu_live/live_decision/poller.py::_trigger_live_decision`:
  new `_record_precondition_check()`, called for both EXECUTE and SKIP
  (being checked and failing is still being tested, per the design
  doc's own wording) with the real `precondition_held` value the agent
  returned -- NOT called for EXTEND_GRACE_WINDOW/error/unrecognized,
  since no real verdict was reached. Best-effort: a failure here is
  logged and swallowed, same posture as every other side-write in this
  codebase (e.g. `MaturityConsultationStore`'s own recording calls) --
  this only affects a strategy's own visibility field, nothing the
  trading loop depends on reading back.
- Found and fixed a real, pre-existing test-isolation gap while adding
  route-level test coverage: `vinu-strategy/vinu_strategy/server/
  routes_read.py`'s `_get_api()` is a lazy, never-reset module-level
  singleton -- the first test in the whole pytest session to construct
  it (via `create_merged_app()`) wins for every test after, in any file,
  regardless of that later test's own env vars. Confirmed concretely: a
  first version of this build's own new route test file, if run before
  `test_merged_app.py`, broke that file's "empty registry" assumption.
  Fixed by resetting the singleton before AND after this build's own new
  test file's fixture (scoped to this file's own tests, not a fix to the
  broader gap, which is real and pre-existing, not introduced here).
- 18 new tests: 10 in new `test_precondition_state.py`
  (`PreconditionStateStore` round-trip, `None` survives the
  INTEGER<->bool conversion, upsert-not-append, `StrategyAPI` overlay
  behavior, a SKIP counting as tested, unknown-strategy 404, confirming
  the YAML file itself is never modified), 4 in new
  `test_routes_precondition_check.py`, 4 in
  `test_live_decision_poller.py`'s new `TestPreconditionWriteBack`
  (EXECUTE and SKIP both call it with the real value, EXTEND_GRACE_WINDOW
  does not, a call failure doesn't crash the cycle). Two existing
  `TestLiveDecisionTrigger` tests' own `_post` mocks were also updated to
  handle the new `/precondition-check` call explicitly rather than
  silently relying on `_record_precondition_check`'s own broad
  exception-swallowing to mask an otherwise-unhandled-URL
  `AssertionError`. Confirmed zero regressions: full `vinu-strategy`
  suite (136 passed, up from 122, +14 exactly, checked stable in both
  file-collection orders after the isolation fix) and full `vinu-live`
  suite (559 passed, up from 555, +4 exactly -- the poller-side tests
  only).
- **Point 6 is now fully closed** — every piece the design doc named is
  built.

## How this file gets updated going forward

Each time a point's table schema and API/tool-call shape get pinned down
(the "plan" step discussed before implementation starts), add a dated log
entry here, update that point's row to "Designed — see `NN-....md`", and
link the new doc. Each time real code lands for a point, update the row
again to "Built — see `path/to/file`" with a one-line pointer to where,
same citation style the rest of this folder already uses. Never mark a
row done from intent alone — only from a real doc (design) or real code
(build).
