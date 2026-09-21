# Implementation log

Running, dated log of what's actually been built from `01-plan.md` —
same convention as `maturity-agentic-system/thinking-1/02-decided-pattern/
05-to-do.md`'s own running log. Read `01-plan.md` for the design; this
file only records what actually happened, in the order it happened,
including any real corrections found while building (the plan's own
design vs. what the real code turned out to need).

Status as of 2026-09-21: build in progress.

## Update — the 3-table schema (01-plan.md section 1)

Built as designed: `vinu-infra/strategy_evaluation.py`
(`StrategyEvaluationStore`, 3 tables, `write_step_result()` as the one
funnel, `seed_step_registry()` with the real 10-step seed data from
`01-plan.md` section 3). 13 new tests
(`vinu-infra/tests/test_strategy_evaluation.py`), full `vinu-infra` suite
green (267/267).

**One real correction found while building `_recompute_status()`**: the
plan's section 1 didn't specify how a *later* PASS should override an
*earlier* FAIL in the status table (e.g. `decay_scan` failing, then a
later re-evaluation passing again after re-research). Implemented as:
history is always authoritative and scanned newest-first for the current
terminal state — a later `decay_scan` FAIL always wins (sets
`decayed`), otherwise the most recent real terminal event
(`capital_allocator`/`shadow_evaluator` PASS → `active`; any FAIL →
`rejected`) decides `status`, not just the furthest step ever reached.

## Update — shared data root (01-plan.md section 2's open question)

**Resolved: option (a) from the plan** — one real shared docker volume,
`./data/strategy-evaluation`, mounted read-write into `agent-api`,
`research-api`, and `live-api` (the three services that own real steps),
each with `VINU_STRATEGY_EVAL_DATA_ROOT=/strategy-eval` set.
`docker-compose.yml` validated after the edit.

## Update — wired so far (01-plan.md section 2's table)

- **`promotion_bar`** (step 2) — `vinu-research/vinu_research/cli.py`'s
  `promote-scan` command. Closes the real gap `00-explanation.md`
  section 3 found (was print-only). New helper
  `_strategy_evaluation_store()` in `cli.py`, resolved fresh from env
  per call (same "don't trust a frozen constant" reasoning already
  established elsewhere in this codebase).
- **`correlation_gate`** (step 3) — wired at **both** real call sites,
  not just one: `cli.py`'s `promote-scan` (reusing the
  `correlation_verdict` it already computes) and
  `vinu-research/vinu_research/service.py`'s `approve_run()` (the other
  real path that creates an artifact from a fresh research run,
  independent of `promote-scan`). Both write real
  `avg_correlation`/`max_correlation`/`n_active` into `metrics_json`.
- **`decay_scan`** (step 7) — `cli.py`'s `_run_decay_scan()`, right
  after each artifact's real `DecaySnapshot` is computed.

New test file: `vinu-research/tests/test_strategy_evaluation_wiring.py`
(3 tests, real `SqliteStrategyStore` + real `_run_decay_scan`/
`promote_scan_main` calls, not mocked). Full `vinu-research` suite green
(933/933, 1 pre-existing skip unrelated to this work).

## Update — `risk_gatekeeper` (step 4) and `order_guard` (step 10) wired

**`risk_gatekeeper`** — `vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py`.
New `_write_evaluation_step()` helper (ships inert when
`VINU_STRATEGY_EVAL_DATA_ROOT` unset). Wired at both real branches:
REJECTED (writes FAIL with the LLM's real reason, right next to the
existing `TickerLedger` write it already had) and APPROVED/PEND (writes
PASS with the real `approved_size`, right after `mark_pend()` succeeds).
3 new tests in `test_risk_gatekeeper_hook.py` (PASS, FAIL, ships-inert).
Full suite green (6/6 in that file).

**`order_guard`** — `vinu-agent/vinu_agent/tools/trade_tool.py`, right
after the real `guard.check(...)` call, the structurally-unbypassable
choke point already verified in `00-explanation.md` section 5.

**Real, documented limitation found while wiring this one**: unlike
every other step, `order_guard` checks a specific *order* (symbol/side/
qty), not a strategy artifact — there is no real `artifact_id` resolved
anywhere in `trade_tool.py`'s own scope for the common case.
`GuardResult.blocked_artifact_ids` (real artifact linkage) exists but is
only populated for operator-limit rejections. Used it when present;
otherwise falls back to a synthetic `f"order:{symbol}"` id, so at least
real per-symbol order-outcome history exists, honestly documented as not
true per-artifact linkage rather than silently faked. `HOLD` added as a
real third verdict for the `needs_reauth` case (near a limit, not over
it) — not just PASS/FAIL. 3 new tests in
`test_trade_tool_audit_trail.py` (PASS, FAIL with real reason,
ships-inert). Full `vinu-agent` suite green (1214/1214, 4 pre-existing
skips unrelated).

## Update — `capital_allocator` (step 5) wired, plus a real correction to `01-plan.md`

`vinu-agent/vinu_agent/agent/capital_allocator_hook.py`. New
`_write_evaluation_step()` helper (same ships-inert shape as
`risk_gatekeeper_hook.py`'s). Wired at three real points:
- The kill-switch-engaged branch → `capital_allocator`, **`HOLD`**
  (funding was decided but execution is held — genuinely neither PASS
  nor FAIL, the real third verdict this schema has for exactly this
  shape).
- The real funding-succeeds branch (`mark_active` succeeds) →
  `capital_allocator`, `PASS`.

**Real correction to `01-plan.md`'s own table, found while reading this
file**: `promotion_bar` (step 2) has **three** real call sites, not one
— `cli.py`'s `promote-scan`, `service.py`'s `approve_run()` (both
already wired), and **this file**, which independently re-checks
`meets_promotion_bar()` before funding (a real, deliberate second
enforcement point — the file's own docstring explains why: funding used
to be able to override a failing statistical bar, which was a real gap,
G1 in `research-discussion-v1/complete-plan/01-native-gaps.md`). Wired
here too, third site.

3 new tests in `test_capital_allocator_hook.py` (funded → PASS+PASS,
promotion-bar failure → FAIL + funding correctly skipped, halted →
HOLD). Full suite green (30/30 combined with `test_capital_allocator_worker.py`).
Full `vinu-agent` suite green (1217/1217, 4 pre-existing skips
unrelated).

## Real steps wired so far: 6 of 10

`promotion_bar` (3 real call sites), `correlation_gate` (2 real call
sites), `decay_scan`, `risk_gatekeeper`, `order_guard`,
`capital_allocator`. All with real tests. All suites green:
`vinu-infra` (267), `vinu-research` (933), `vinu-agent` (1217).

## Update — `risk_critic` (step 1) wired, resolving the open design question

`vinu-research/vinu_research/service.py`'s `approve_run()`. Real
resolution to the question `01-plan.md` flagged: the loop's iterative
refinement never persisted the full `CriticFeedback` anywhere durable
(confirmed again) — but `iteration_checkpoints.critic_verdict` (a real,
already-existing column, `storage/sqlite_backend.py`) *does* persist the
final iteration's verdict string via `get_last_checkpoint(run_id)`,
which `approve_run()` already has `run_id` for. Used that. **Honest
limitation, not hidden**: only the verdict string survives, not
`CriticFeedback.reasoning`'s actual text — the `reasoning` field records
this explicitly (`"full reasoning text not persisted in run storage"`)
rather than inventing content. 2 new tests in `test_service.py` (PASS
from a real checkpoint, FAIL for a STOP verdict). Full `vinu-research`
suite green (935/935).

## Update — real fix to order_guard's artifact_id (was a known limitation, now closed)

`vinu-agent/vinu_agent/tools/trade_tool.py`. The synthetic
`f"order:{symbol}"` fallback documented earlier is now only a genuine
last resort. New `_resolve_active_artifact_id(symbol)` reuses the exact
same in-process lookup `OrderGuard._check_active_artifact()` already
does (`research_link.get_strategy_store()` +
`list_artifacts_for_symbol(symbol, statuses=[ACTIVE])`) — real artifact
linkage for the common case, synthetic id only when genuinely no ACTIVE
artifact exists (e.g. `require_active_artifact: false`). New test proves
the real resolution path, not just the fallback
(`test_passed_order_resolves_the_real_active_artifact_id`). Full
`vinu-agent` suite green (1218/1218 at that point).

## Update — the K-cap fix (01-plan.md section 4)

**Real complication found that changed the plan**: Option B (derive the
cap from `strategy_evaluation_status`) needs a join from a
`candidate_proposed` ledger event to an artifact_id — but
`on_propose()`'s `ref_id` (`planner_triage_hook.py`) is a **research-run
id**, not an artifact_id (an artifact doesn't exist yet at proposal
time). That join doesn't exist and wasn't in scope to build this pass.
**Built Option A instead** (rolling time window) — the honestly-scoped,
buildable fix: `thesis_intake_gate.py` gained `K_CAP_WINDOW_DAYS = 7`
(provisional, not tuned, same disclaimer as `K_CAP_DEFAULT` itself) and
`_k_cap_window_since()`; both real call sites that share this K-cap
counter (`thesis_intake_gate.py`'s own `check()` and
`planner_triage_hook.py`'s `check()`) now pass `since=` to
`count_events()`. Real regression test proves the actual bug: 3 events
backdated 13 days (matching AAPL's real state found live) no longer
count against the cap; 3 recent events still do. 2 new tests in
`test_planner_triage_hook.py`, using the real `TickerLedgerStore`, not
just the fake. Full `vinu-agent` suite green (1220/1220).

**Option B remains the more correct long-term fix** (a genuinely-still-
open candidate shouldn't age out just because it's been a week; a
resolved one should free its slot immediately, not after 7 days) — left
as a real follow-up once the run_id→artifact_id join gets built,
documented here rather than silently treated as fully solved.

## Real steps wired: 7 of 10

`risk_critic`, `promotion_bar` (3 real call sites), `correlation_gate`
(2 real call sites), `decay_scan`, `risk_gatekeeper`, `capital_allocator`,
`order_guard`. All suites green: `vinu-infra` (267), `vinu-research`
(935), `vinu-agent` (1220).

## Update — `shadow_evaluator` (step 6) wired

`vinu-live/vinu_live/shadow_evaluator.py`'s `_evaluate_one()`. New
`_write_shadow_evaluation()` helper. Writes at both real terminal
outcomes: `auto_paused` (real Sharpe-collapse fast-path, FAIL) and the
normal `promoted`/`below_threshold` split (PASS/FAIL). `insufficient_data`
deliberately writes nothing — nothing has actually been decided yet (not
enough paper-trading days accumulated), same "no evidence, no claim"
posture `population_stability_index()` uses for empty inputs. Ticker
resolved from the real `artifact["universe"][0]` the `/research/artifacts`
endpoint already returns. 3 new tests (PASS, FAIL, insufficient-data
writes nothing). Full `vinu-live` suite green (445/445).

## Update — `trade_score_gate` (step 8) and `approve_trade_plan` (step 9) wired

Both in `vinu-research/vinu_research/trade_plan_authoring.py`'s
`approve_trade_plan()` — the one real function that owns both checks
(confirmed via its own docstring: `check_trade_score_gate` has no
approver/force logic of its own specifically because `approve_trade_plan`
already applies it uniformly across both gates). New `_write_eval()`
local closure, called at every real decision point:
- `trade_score_gate`: the frozen-tier re-check (PASS/FAIL).
- `approve_trade_plan`: **either** of its two real branches — the
  bootstrap path (no calibration history yet, checks the symbol's own
  ACTIVE strategy) or the `CalibrationGate` path (real calibration
  history exists) — whichever one the real artifact state routes
  through.

**Real design decision made explicit, not silently guessed**: `force=True`
records the gate's own real underlying verdict (FAIL), not a
silently-flipped PASS — `force`/`approver` go into `metrics_json`
instead, so a forced override is distinguishable from a gate-cleared
one after the fact, mirroring this function's own existing audit-log
convention for exactly that distinction. Confirmed by a dedicated test
(`test_forced_approval_still_records_the_real_underlying_verdict`).
Also confirmed: a `trade_score_gate` FAIL correctly short-circuits
before `approve_trade_plan`'s own check ever runs (no phantom PASS/FAIL
row for a step that never actually executed). 5 new tests in
`test_trade_plan_authoring.py`. Full `vinu-research` suite green
(940/940 — one `test_concurrent_writes` failure observed once, confirmed
flaky/timing-sensitive on a re-run, not a real regression from this work).

## Real steps wired: 10 of 10

Every step in `01-plan.md`'s table is now wired: `risk_critic`,
`promotion_bar` (3 real call sites), `correlation_gate` (2 real call
sites), `risk_gatekeeper`, `capital_allocator`, `shadow_evaluator`,
`decay_scan`, `trade_score_gate`, `approve_trade_plan`, `order_guard`
(with real artifact-id resolution). All suites green across all 4
touched packages: `vinu-infra` (267), `vinu-research` (940), `vinu-agent`
(1220), `vinu-live` (445).

## Update — the enhancer loop itself, DONE

**Real, simpler trigger point than the plan guessed**: not a new hook —
`scheduler_workers.py`'s `make_planner_on_yes()`'s `_on_yes()` already
fires exactly once per real candidate proposal, and it **already had
the right shape**: it was already feeding `HypothesisRegistry`'s
`prior_rejections` into the `idea_generator` hand-off's task string.
Extended that exact, already-proven mechanism rather than inventing a
new one.

New `_strategy_evaluation_context_for_ticker(ticker)` appends, when real
data exists: (1) every other candidate still `in_progress`/`active` for
the ticker, and (2) the single most recent real rejection's
`rejected_at_step` + `rejected_reason` from the machine-evaluation
chain (distinct from `HypothesisRegistry`'s human-thesis rejections,
untouched).

**All three of the plan's open design questions resolved by this real
choice, not left open**:
- Prompt shape → reused the exact pattern already proven in production.
- How much history → only the single most recent rejection, not the
  full history.
- Unbounded growth → naturally bounded by `K_CAP_DEFAULT` itself (at
  most 3 in-flight siblings can ever exist per ticker) — no separate cap
  needed.

3 new tests in `test_scheduler_workers.py`. One real correction made
while adding them: my first edit attempt accidentally split
`TestMakePlannerOnYes` by inserting the new test class in the middle of
it — caught by running the full file (48 expected, structural check),
fixed by moving the misplaced test back to its own class before
re-verifying. Full `vinu-agent` suite green (1223/1223).

## Final status: every real piece of 01-plan.md is built

All 10 evaluation steps wired, the K-cap bug fixed (Option A, real and
verified), and the enhancer loop itself feeding real sibling/failure
context into new candidate proposals. All 4 touched packages green:
`vinu-infra` 267, `vinu-research` 940, `vinu-agent` 1223, `vinu-live` 445.

## Update — the read view, DONE

New `vinu-agent strategy-eval <TICKER>` CLI command
(`vinu_agent/cli.py`'s `_cmd_strategy_eval`). For a ticker, prints every
real candidate, how far it got, and for each step: verdict + the
specific real reasoning recorded for *that* candidate. For any `FAIL`
specifically, also prints the general rule from
`strategy_evaluation_step_registry` and the real source file — so a
rejection is readable end to end (what happened, and what the rule
actually is) without reading code. This is the literal "table where you
can see what passed, what failed, and why" originally asked for.

Real output, confirmed live:
```
AAPL
====

Artifact: art-1  status=rejected  furthest_step=1
  [PASS] risk_critic          final iteration critic_verdict=PASS
  [FAIL] promotion_bar        deflated_sharpe 0.1 below threshold 0.3
      rule:   deflated_sharpe >= config threshold AND holdout_passed (if required) AND pbo <= config threshold.
      source: vinu-research/vinu_research/promotion.py:30
```

9 new tests in `test_cli_strategy_eval.py` — including a real, specific
check that the rule dump only appears under a `FAIL` row, never under a
`PASS` one, and only under the step that actually failed (not the whole
candidate). Full `vinu-agent` suite green (1232/1232).

## Update — K-cap fix replaced: Option A (time window) → Option B (real artifact count)

**User correction, 2026-09-21**: Option A's `run_id→artifact_id` join
was never actually needed — the premise that blocked it earlier
("no join from a `candidate_proposed` ledger event to an artifact_id")
was solving the wrong problem. The cap doesn't need to count *proposal
events* at all; it needs to count **currently-open artifacts for the
ticker**, and that machinery already existed and was already used
elsewhere in the same function for recipe rotation:
`strategy_store.list_artifacts_for_symbol(ticker, statuses=
NON_TERMINAL_STATUSES)`. The whole system is already organized around
`artifact_id` (machine-proposed and human-submitted strategies both
produce the same `Artifact`), so counting artifacts directly is the
real fix, not an approximation of one.

Replaced in both real call sites:
- `thesis_intake_gate.py`'s `check()` — when `strategy_store` is
  provided, counts `len(list_artifacts_for_symbol(ticker,
  NON_TERMINAL_STATUSES))` instead of the old
  `ticker_ledger.count_events(..., since=_k_cap_window_since())`.
  `K_CAP_WINDOW_DAYS`/`_k_cap_window_since()` are **kept**, not deleted
  — real fallback for the one caller path where no `strategy_store` is
  available. `NON_TERMINAL_STATUSES` moved here from
  `planner_triage_hook.py` as the shared/upstream definition.
- `submit_thesis_tool.py` — `ThesisIntakeGate(...)` now passes
  `strategy_store=self._strategy_store` (already available on the tool,
  previously constructed but unused for this).
- `planner_triage_hook.py`'s `check()` — rewritten to use the same
  `list_artifacts_for_symbol` count directly; the old
  `count_events(..., since=...)` block, `K_CAP_WINDOW_DAYS`/
  `_k_cap_window_since` imports, and the unused `ArtifactStatus` import
  were all removed (dead now that the count is artifact-based).

**No time-based control needed at all**: decay (`decay_scan`, step 7)
already auto-transitions a strategy to `decayed`/`disabled` when it's
no longer working, which frees its K-cap slot the moment that happens
— not after some arbitrary window. A fixed cap of currently-open
artifacts, with decay doing the real-time freeing, is the complete
mechanism; no separate rolling-window heuristic sits on top of it
anymore.

**A real gap this surfaced, closed with explicit "go ahead"**:
artifact-count-based capping only works if rejected candidates actually
*become* terminal — before this round, a `promotion_bar` FAIL left the
artifact stuck in `BENCHING` forever, silently occupying a K-cap slot
permanently. Fixed by transitioning to `ArtifactStatus.DISABLED` (a
real, already-used terminal state — see `vinu-research/decay.py`'s
`transition_status()`) at all **three** real `promotion_bar` call
sites:
- `cli.py`'s `promote-scan` (was print-only "hold", now sets
  `DISABLED` and persists).
- `capital_allocator_hook.py`'s promotion-bar re-check branch (was left
  in `PEND` forever on rejection, now sets `DISABLED` before
  `continue`).
- `server/routes_read.py`'s `POST /artifacts/{id}/promote` route — a
  **fourth real call site**, found while closing this gap, that had
  never been wired for `strategy_evaluation` writes at all in any
  earlier round. Now writes both `promotion_bar` and `correlation_gate`
  results and sets `DISABLED` on a genuine (non-forced) rejection.
  4 new tests in `test_routes_promote_strategy_eval.py` — the first
  test coverage this route has ever had, old or new behavior
  (`test_passing_promotion_writes_pass_and_activates`,
  `test_failing_promotion_writes_fail_and_disables`,
  `test_forced_promotion_does_not_disable`,
  `test_unset_env_ships_inert`).

**Real design split, deliberately not applied uniformly**:
`promotion_bar` FAIL → `DISABLED` (permanent), because
`deflated_sharpe`/`holdout_passed`/`pbo` are fixed metrics from a
backtest that already happened — re-checking later can never change the
verdict. `risk_gatekeeper`/`correlation_gate` REJECTED were
deliberately left re-checkable, not terminated — portfolio state and
inter-strategy correlation can legitimately change over time, so a
rejection today shouldn't permanently block a candidate that might
clear the bar later.

One pre-existing test updated to match the new real behavior:
`test_capital_allocator_hook.py::TestPromotionBarGate::
test_artifact_failing_promotion_bar_is_not_activated` — assertion
changed from `ArtifactStatus.PEND` to `ArtifactStatus.DISABLED`, with
the explanatory comment rewritten to describe why, not just what.

Full suites green after this round: `vinu-infra` 267, `vinu-research`
944, `vinu-agent` 1234.

## Still open (real, not silently closed)

- **Manual/documented verification** (`01-plan.md` section 7) — run the
  real end-to-end pass (main stack + a K-cap-affected ticker) and
  confirm `strategy_evaluation_status` reports accurately against what
  actually happened. Not yet done against a real running stack, only
  against unit/integration tests with real store objects.
- The `strategy-eval` command's output is plain text for a human reading
  a terminal — no JSON/machine-readable mode yet, if something else
  ever needs to consume this programmatically.
