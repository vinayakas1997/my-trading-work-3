# Implementation status — what is done, what files were touched

Tracks `03-implementation-plan.md`. Updated after every piece of work: status, files touched, tests, and anything
found or decided on the way. Newest entries at the bottom of each section. Nothing is committed to git unless noted.

Legend: DONE · IN PROGRESS · NEXT · WAITING (needs your decision) · BLOCKED

## Phase overview

| Phase | What | Status |
|---|---|---|
| 0 | Audits and plan (docs only) | DONE |
| 1 | Edge manifest + static check (read-only) | **DONE 2026-10-02** |
| 2 | Fixes that need no decision | **DONE 2026-10-03** (2.1, 2.2, 2.3, 2.4a-e, 2.5) |
| 3 | Runtime recorder + report (first slice: the vinu-live money path) | **DONE 2026-10-03** (8 of 31 wired edges instrumented, see below) |
| 4 | Decisions that change live behavior (A1, A2, A5, A6, A7, A8, v1 A8, B1) | **DONE as opt-in flags** (all eight; switching them on is an operations decision) |
| 5 | New safeguards (lookahead, warmup, uncertainty, novelty, parity, lockout) | **IN PROGRESS** (5.1 features, 5.2, 5.3 done) |
| 6 | Enforcement once data exists | not started |

---

## Phase 0 — docs written (no code)

| File | Action | Note |
|---|---|---|
| `other-repos-world/comprison-other-vinu/01-freqtrade.md` | modified (appended addendum) | Freqtrade second pass, 2026-10-02 |
| `other-repos-world/repo-list.md` | modified (one table row) | Freqtrade row re-checked note |
| `newer-thinking-with-discussed/the-inconsistencies-v2/01-inconsistencies-v2.md` | created, then appended UPDATE | v2 gaps vs vision; corrections after code read |
| `newer-thinking-with-discussed/the-inconsistencies-v2/02-logic-audit-2026-10-02.md` | created | code-verified findings A1-A6, B1-B2, 0.1 |
| `newer-thinking-with-discussed/the-inconsistencies-v2/03-implementation-plan.md` | created | six-phase plan |
| `newer-thinking-with-discussed/the-inconsistencies-v2/04-implementation-status.md` | created | this file |

---

## Phase 1 — Edge manifest and static check — DONE

**Goal:** a declared list of "what must flow where" on the money path, checked against the real source so a missing
producer→consumer connection fails the build.

**Files touched (all inside `vinu-components/vinu-infra/`):**

| File | Action | Purpose |
|---|---|---|
| `pipeline_edges.yaml` | created | the manifest: 28 edges, each with producer / consumer / purpose / cadence / `empty_ok` / `status` (`wired` or `gap` + `gap_ref`) |
| `pipeline_edges.py` | created | loader + checker + report (`python -m vinu_infra.pipeline_edges`); read-only, no service imports, no runtime side effects |
| `tests/test_pipeline_edges.py` | created | 18 tests: checker semantics in `tmp_path`, manifest validation, and one test over the **real** manifest and source tree |

No existing source file was modified.

**How it works:** `wired` edges must keep a call-shaped reference in the consumer's non-comment source (regression
check). `gap` edges must carry an audit reference and must NOT be referenced yet; the day someone wires one, the test
fails with `DRIFT_NOW_WIRED` and tells you to flip it to `wired`, so the manifest cannot rot in either direction.
Renamed or deleted files fail as `STALE`.

**Result on first run (verified against the code, not just the audit):** 28 edges — 21 wired, 7 known gaps, 0 drifted or stale.

| Known gap (still unwired in code) | Audit ref |
|---|---|
| `portfolio.daily_allocation → live.scheduler` | logic-audit A1 |
| `guard.cooldown → live.scheduler` | A4 |
| `guard.turbulence → live.scheduler` | A4 |
| `guard.data_freshness → live.scheduler` | A4 |
| `order.reduce_only → live.scheduler` | A5 |
| `book.writes → live.scheduler` | A6 |
| `precondition_held → live.scheduler` | v1 A8 |

**Tests:** `vinu-infra` 350 → **368 passed** (+18, 0 failed, same 2 pre-existing warnings).

**Limits to keep in mind:**
- Matches are plain substrings on non-comment lines. A token inside a docstring still counts; tokens were chosen to be
  call-shaped (`/portfolio/daily-allocation`, `cooldown_active(`) to keep that rare.
- It proves a consumer *references* its producer, not that the value is correct or fresh. Runtime freshness is Phase 3.
- Covers the money path only. Other services (stock-price, news, screener internals, the 30 angles) are not in the manifest.
- A2 (executor symbol ownership) and B1 (confidence triple-count) from the audit are logic/design issues, not
  connection gaps, so they are not manifest edges.

**To run the report:** `cd vinu-components/vinu-infra && python -m vinu_infra.pipeline_edges`

---

## Phase 2 — Fixes that need no decision — NEXT

Order (each flips a manifest edge and adds tests; update this table as they land):

| # | Item | Edge it flips | Status |
|---|---|---|---|
| 2.1 | Fail-closed approval: reject a plan whose `expected_drawdown` and `cvar_95_limit` are both 0 (audit B2) | n/a (logic) | **DONE 2026-10-02** |
| 2.2 | Share guards across both paths: data-freshness, cooldown, turbulence, called from the scheduler, **entries only**, opt-in (audit A4) | `guard.cooldown/turbulence/data_freshness->live.scheduler` | **DONE 2026-10-02** |
| 2.3 | Stop / max-hold for live-decision positions, optional config, default off (audit A3) | `strategy.stop_rules->live.poller`, `live_decision.entry_price<-live.scheduler` (new, wired) | **DONE 2026-10-03** |
| 2.4a | Stuck live-decision triggers: retry, then expire + notify (v1 C1; found a worse bug, see below) | `live_decision.stuck_trigger->agent.notify` (new, wired) | **DONE 2026-10-03** |
| 2.4b | Unsized-EXECUTE queue (v1 C2) | `live_decision.unsized_executes->live.api` (new, wired) | **DONE 2026-10-03** |
| 2.4c | `code_hash` into sweep rows + graveyard join (v1 A4), `param_diff` persisted (v1 A3) | `sweep.base_code_hash->research.graveyard` (new, wired) | **DONE 2026-10-03** |
| 2.4d | Degraded-run / unfunded-sleeve visibility (v1 C4) | `portfolio.not_funded_history->portfolio.api`, `strategy.run_quality->strategy.runs_api` (new, wired) | **DONE 2026-10-03** (scoped, see below) |
| 2.4e | Forecast + refinement prompt inputs (v1 B3, B4), **partial by design** | n/a | **DONE 2026-10-03** (two slices, see below) |
| 2.5 | Fail-open / fail-closed matrix (v1 C3), doc only | n/a | **DONE 2026-10-03** |

Notes for 2.2: guards must never block exits. The exit-exemption work (audit A5) is Phase 4 and needs your go-ahead;
until then the shared guards only gate instructions that **increase** exposure.

### 2.1 Fail-closed approval — DONE 2026-10-02 (audit B2)

**Problem:** `_build_risk_band` returns an all-zero `RiskBand` when risk state is unavailable. Every Trade Score
sub-check then fails open on that zero (reward:risk veto skipped, risk score neutral, EV loses its loss term), so the
plan clears the tier gate on inflated EV and could be approved. It cannot enter (the live path skips a zero size), so
the harm was an inert ACTIVE plan holding a portfolio slot, but the hard reward:risk floor was bypassable by a data hole.

**Change:** `approve_trade_plan` now rejects a plan that carries a Trade Score but has both `expected_drawdown` and
`cvar_95_limit` at 0 (reason prefix `risk_not_computed`). Either field positive is enough (older plans only have
`cvar_95_limit`). `force=True` + `approver` overrides, like every other gate there. The rejection is written to
`strategy_evaluation` as a `trade_score_gate` FAIL row. Plans with no Trade Score at all stay fail-open (same
"never backfilled" convention the tier check already uses).

**Files touched (inside `vinu-components/vinu-research/`):**

| File | Action |
|---|---|
| `vinu_research/trade_plan_authoring.py` | modified, +36 lines, inside `approve_trade_plan` only |
| `tests/test_trade_plan_authoring.py` | modified: new `TestApproveRequiresComputedRiskBand` (7 tests); one existing test (`test_approve_allows_watch_tier_to_pass_default_calibration_bootstrap`) now gives its scored plan a computed risk band, since it scored a plan on a zero band, which is exactly what is now rejected |

**Tests:** `vinu-research` 1185 → **1192 passed** (+7). Mutation check: with the source change reverted, 2 of the new tests
fail (rejection, evaluation-row write) and the other 5 pass as guard cases; fix restored afterward. Same single failure
before and after (see below).

**Behavior change to know about:** a plan whose risk state was unavailable now stays CREATED. The approval worker
retries every cycle and re-notifies each time (existing behavior, tracker item A33), so such a plan will notify
repeatedly until re-authored or force-approved.

**Pre-existing failure, unchanged, not caused by this work:** `tests/test_empty_meanings.py::TestAgentEvalEmptySpelling::
test_unset_env_is_inert_empty_string` fails with `ModuleNotFoundError: vinu_agent` — that v1 C5 contract test imports
`vinu_agent`, which is not installed in the research test environment. It contradicts the "3-environment isolation"
rule the research package otherwise follows; worth moving or guarding with `pytest.importorskip` (not done here, it is
outside this item).

### 2.2 Entry guards on the scheduler path — DONE 2026-10-02 (audit A4)

**Problem:** the trade-plan orchestrator pauses NEW exposure on a consecutive-loss cooldown, a stale price feed and
extreme 14-day realized vol. `LiveScheduler` (portfolio weights + live-decision EXECUTEs) had none of the three, and
sized 15m decisions off the last daily close with no age check.

**Change:** `LiveScheduler._apply_entry_guards` runs right after `translate()` and drops only instructions that
**increase** exposure (opens, adds, or flips into a larger opposite position) when a guard fires. Reducing or closing
instructions always pass. Each guard reuses the orchestrator's own function and threshold
(`cooldown_active`, `turbulence_active`, `PRICE_MAX_AGE_HOURS`), so there is one policy, not two drifting copies.
Held-back symbols are listed in the cycle result as `guard_blocked` and excluded from the expected-position set so
reconciliation does not raise false "drift" alerts. Any error inside the guards fails open (instructions untouched).
`_fetch_prices` now also records each symbol's newest `bar_ts` (and drops it when the bar has none, so the freshness
guard fails open instead of blocking on a lingering old value).

**Opt-in, default off:** `LiveConfig.scheduler_entry_guards_enabled` /
`VINU_LIVE_SCHEDULER_ENTRY_GUARDS_ENABLED`. It changes live order flow, so it follows the plan's rule for such changes.
With the flag off, behavior is byte-for-byte what it was (verified by a test and by the 41 existing scheduler tests).

**Design note (deviation from the plan text):** the plan said to move the guards into `trade_plan/guards.py`. They stay
in `orchestrator.py` and the scheduler imports them, which is the pattern `scheduler.py` already used for its other
shared thresholds, and avoids moving code that existing orchestrator tests import. Only the new pure classifier
`instruction_increases_exposure` went into `guards.py`.

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-live/vinu_live/scheduler.py` | modified, +96 lines: imports, `_last_price_ts`, `_apply_entry_guards`, `_fetch_recent_closes`, call in `cycle()`, expected-position exclusion, `bar_ts` capture in `_fetch_prices` |
| `vinu-live/vinu_live/trade_plan/guards.py` | modified, +17 lines: `instruction_increases_exposure` |
| `vinu-live/vinu_live/config.py` | modified, +11 lines: `scheduler_entry_guards_enabled` + env var |
| `vinu-live/tests/test_scheduler_entry_guards.py` | created, 22 tests (classifier truth table, off-by-default, each guard, reduce never blocked, fail-open, `bar_ts` capture, three end-to-end `cycle()` cases) |
| `vinu-infra/pipeline_edges.yaml` | modified: three `guard.*->live.scheduler` edges flipped `gap` -> `wired` (the manifest test failed with `DRIFT_NOW_WIRED` until I did, as designed) |

**Tests:** `vinu-live` 577 -> **599 passed** (+22), same 3 pre-existing errors in
`test_shadow_evaluator_real_endpoint.py` before and after. `vinu-infra` stays 368 passed. Mutation check: with the
"never gate a reduce" rule disabled, 4 of the new tests fail; restored afterward.
Edge manifest: 21 wired / 7 gaps -> **24 wired / 4 gaps** (`daily_allocation`, `reduce_only`, `book.writes`,
`precondition_held` remain).

**Limits to know:**
- The cooldown reads the trade-plan book's closed positions, and the scheduler path does not write its own fills to that
  book (audit A6), so on this path the cooldown reflects plan-path losses only. Fixing A6 makes it meaningful.
- This does NOT make exits exempt from halts, the spread gate or the event blackout on the scheduler path. That is audit
  A5 (Phase 4, needs your go-ahead).
- Enabling the flag is a deployment decision; nothing turns it on.

**Pre-existing, unrelated:** the 3 `test_shadow_evaluator_real_endpoint.py` errors (fixture-level; not investigated).

### 2.3 Stop / max-hold for live-decision positions — DONE 2026-10-03 (audit A3)

**Problem:** a position opened by a live-decision EXECUTE had no per-position protection. A trade-plan position gets a
broker-side backstop stop plus invalidation and time-stop rules; this one only had the LLM review every N bars and
portfolio-level halts.

**Change:** two optional per-strategy fields, both **0 = off** (like `live_decision_position_size`, there is no safe
invented number, so the strategy author opts in):
- `live_decision_stop_pct` — exit when price moves this fraction against the entry (long: close <= entry x (1 - pct);
  short, i.e. negative size: close >= entry x (1 + pct)).
- `live_decision_max_hold_bars` — exit once this many bars have elapsed since the position opened.

The poller checks them on every new candle for the pair (no LLM call) and closes with the same `close_position` an agent
EXIT uses, so the next scheduler cycle omits the weight and the existing not-targeted rule sells it. It also records a
normal `EXIT` decision (`reasoning: rule_exit:<rule> -- ...`) so history and the agent's anti-flip-flop context see it.
A rule can only exit on inputs it can fully justify: no entry price, a non-finite price, or a zero field disables that
rule rather than guessing. Stop is reported before max-hold when both breach. All of it fails open and never raises
into the poll loop.

The stop needs an entry reference, so `live_decision_open_positions` gets a nullable **`entry_price`** column (migration,
`SCHEMA_VERSION` 4 -> 5; old databases migrate on open and stay readable). The scheduler stamps it **write-once** on the
first priced cycle after the position opens (`set_entry_price_if_missing`), best-effort, never affecting orders.

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-strategy/vinu_strategy/models/strategy.py` | modified, +16: two fields, known-keys, parsing (null in YAML = off) |
| `vinu-strategy/vinu_strategy/api.py` | modified, +2: both fields in the strategy response |
| `vinu-live/vinu_live/live_decision/position_rules.py` | **created**: pure `evaluate_position_rules` |
| `vinu-live/vinu_live/live_decision/schema.py` | modified, +5: `entry_price` on the position dataclass |
| `vinu-live/vinu_live/live_decision/storage.py` | modified, +24: migration, schema version 5, row mapper, `set_entry_price_if_missing` |
| `vinu-live/vinu_live/live_decision/poller.py` | modified, +54: `_apply_position_rules`, called per new candle |
| `vinu-live/vinu_live/scheduler.py` | modified: `_record_live_decision_entry_prices`, called after prices are fetched |
| `vinu-live/tests/test_live_decision_position_rules.py` | **created**, 22 tests (pure rules, write-once and migration of an old DB, scheduler stamping, poller direct, full `cycle()` end to end) |
| `vinu-strategy/tests/test_live_decision_protection_fields.py` | **created**, 6 tests (defaults, parsing, null, no unknown-key warning, API exposure) |
| `vinu-infra/pipeline_edges.yaml` | modified: two new `wired` edges |

**Tests:** `vinu-live` 599 -> **621 passed** (+22); `vinu-strategy` 131 -> **137 passed** (+6); `vinu-infra` stays 368.
Failures/errors unchanged and pre-existing: vinu-live 3 errors (`test_shadow_evaluator_real_endpoint.py`); vinu-strategy 10
errors (`ModuleNotFoundError: vinu_portfolio` in the merged-app / simulator route tests, an environment issue).
Mutation checks: allowing the entry price to be overwritten fails `test_entry_price_is_write_once`; removing the poller call
fails the full-cycle test; both restored afterward. Edge manifest: 30 edges, 26 wired, 4 known gaps.

**Limits to know:**
- `entry_price` is the last daily close the order was sized on at the first priced cycle, not the broker fill price.
- "Bars held" is calendar time in bar units (same convention as the state tracker's grace window), so overnight and weekend
  gaps count as bars on intraday timeframes. Choose `live_decision_max_hold_bars` with that in mind.
- The stop is checked on candle closes, not tick by tick, and exits through the scheduler's next cycle (hourly by default),
  so it is slower than the orchestrator's broker-side backstop stop. It adds a floor; it does not replace one.
- Exits on the scheduler path can still be delayed by halts and the spread / event gates (audit A5, Phase 4).
- No strategy file was changed, so nothing is switched on; a strategy author sets the fields in its YAML.

### 2.4a + 2.4b Stuck live-decision triggers and the needs-sizing queue — DONE 2026-10-03 (v1 C1, C2)

**2.4a. The bug (worse than v1 C1 described).** When the live-decision call failed (HTTP error, timeout) or returned
something unrecognized, the pair stayed `ready_to_execute` **forever**. The poller only triggers on a fresh transition
into that stage, and the state tracker deliberately never re-evaluates a ready pair, so the log line "will retry next
cycle" was false and that (ticker, strategy) could never fire again until someone intervened. v1 C1 described it as
"retries forever with no alert"; in fact it never retried at all.

**Change:** while a pair is still `ready_to_execute` from an earlier candle, the poller now retries on each later candle
(one attempt per candle is a natural backoff). Attempts are counted from the existing append-only `live_decisions` table
(error / unrecognized / EXTEND_GRACE_WINDOW count; EXECUTE / SKIP resolve a trigger) so there is no counter to keep in
sync. At `live_decision_max_trigger_attempts` (default 3) the trigger is expired (`state_tracker.mark_expired`, terminal,
so the pair resets to idle and can fire again with a new trigger), a "gave up" row is recorded, and one notification is
sent (reuses `/notify/reconciliation-drift` with `action="live_decision_stuck"`, the same reuse pattern the scheduler's
target-weight-drift alert uses). `VINU_LIVE_DECISION_MAX_TRIGGER_ATTEMPTS=0` restores the old never-retry behavior. The two
misleading log lines were corrected.

**2.4b.** `list_needs_sizing` returns EXECUTE decisions that were marked applied but never became a position (the strategy
has no `live_decision_position_size`): a read-time anti-join against the open-positions table (any status), so no new
table or flag, and it drains by itself once a size is configured and a later EXECUTE opens a position. Exposed at
`GET /live/decisions/needs-sizing` and as a `needs_sizing` count in the scheduler's cycle result.

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-live/vinu_live/live_decision/poller.py` | modified: `_retry_or_expire_unresolved`, `_notify_stuck_decision`, retry branch in `cycle()`, two log lines corrected |
| `vinu-live/vinu_live/live_decision/state_tracker.py` | modified: `mark_expired` |
| `vinu-live/vinu_live/live_decision/storage.py` | modified: `count_unresolved_decision_attempts`, `list_needs_sizing`, `_row_to_decision` |
| `vinu-live/vinu_live/config.py` | modified: `live_decision_max_trigger_attempts` + env var |
| `vinu-live/vinu_live/server/app.py` | modified: `GET /live/decisions/needs-sizing` |
| `vinu-live/vinu_live/scheduler.py` | modified: `needs_sizing` count in the cycle result |
| `vinu-agent/vinu_agent/server/routes_notify.py` | modified: `detail` field and a `live_decision_stuck` message branch |
| `vinu-live/tests/test_live_decision_stuck_and_needs_sizing.py` | **created**, 16 tests (attempt counting, anti-join, `mark_expired` unsticks the pair, full poller scenarios: retry, give up + notify + recover, limit 0, notify failure, resolved never retried, route + no route shadowing) |
| `vinu-agent/tests/test_routes_notify.py` | modified: +1 test for the stuck-decision message |
| `vinu-infra/pipeline_edges.yaml` | modified: two new `wired` edges |

**Tests:** `vinu-live` 621 -> **637 passed** (+16), same 3 pre-existing errors. `vinu-agent` notify file 15 -> 16.
Mutation check: restoring the old "no retry for a still-ready pair" behavior fails 4 of the new tests (the limit-0 test passes,
as it should, since it asserts the old behavior); restored afterward. Edge manifest: 32 edges, 28 wired, 4 gaps.

**vinu-agent full suite:** 1496 passed, 16 failed, 2 errors, all in `test_llm.py`, `test_service.py`,
`test_capital_allocator_hook.py`. Verified pre-existing: with my two agent files stashed, those three files give the identical
16 failed / 2 errors. Not caused by this work and not investigated (looks like OpenAI-SDK / environment issues).

**Behavior change to know about:** a pair whose agent call failed is now retried (up to 3 attempts, one per candle) and then
expired, where before it hung. A retried call that finally returns EXECUTE can now place an order that previously could not
happen for that stuck pair. That is the intended behavior, but it is a live-order-flow change that is ON by default; set the
env var to 0 to disable.

### 2.4c `code_hash` join and persisted `param_diff` — DONE 2026-10-03 (v1 A4, A3)

**A4 problem:** the generation store wrote `code_hash` (indexed, with `find_by_code_hash`) but nothing ever queried it, and a
sweep recorded params but never which code it varied, so a generation-time discard could not be linked to a later sweep of the
"same" candidate.

**A3 problem:** `param_diff_from_winner` was computed live for the HTTP response and discarded; nothing could read "why did this
lose, how far from the winner" later.

**Change (all additive, nullable, backfill-safe; `SweepGridStore` schema v1 -> v2 via migrations):**
- `sweep_runs.base_code_hash` — hash of the base code a **base-code-mode** sweep varied, using the **same** `code_hash` function
  as the generation store, so one identifier joins both. Recipe-mode sweeps have no base code and never join.
- `sweep_grid_points.code_hash` — hash of the exact (parameter-substituted) code a succeeded point executed.
- `sweep_grid_points.param_diff_json` — `param_diff_from_winner` for every non-winner point, failed points included (how far
  the failed point was from the winner). The winner stores none.
- `get_sweep` (and so `GET /research/sweep/grid/{sweep_id}`) now returns `base_code_hash`, per-point `code_hash` and
  `param_diff_from_winner`. New `find_sweeps_by_base_code_hash`.
- Graveyard join, both directions, read-only: a discarded generation candidate lists the sweeps that later varied it
  (`swept_in`); a failed sweep point lists the generation rounds behind its base code (`generation_ids`) and its
  `param_diff_from_winner`.
- `run_sweep_grid` passes `base_code` through to the store.

**Deliberately not done:** v1 A3 also suggested listing sweep **winners** in the graveyard (`source=sweep_winner`). A winner is not
a dead idea, so it would blur what the graveyard means; the "how far from the winner" question is answered by the persisted diff
on the losers instead. The graveyard is still a query, not a gate (graveyard-as-blocker remains a separate decision).

**Files touched (inside `vinu-components/vinu-research/`):**

| File | Action |
|---|---|
| `vinu_research/sweep_store.py` | modified: schema v2 + migrations, hashes and diffs on write, new fields on read, `find_sweeps_by_base_code_hash` |
| `vinu_research/sweep_grid.py` | modified: passes `base_code` to `record_sweep` |
| `vinu_research/candidate_graveyard.py` | modified: both-direction join fields; docstring updated |
| `tests/test_sweep_code_hash_and_param_diff.py` | **created**, 16 tests (hash agreement with the generation store, per-point hashes, recipe mode, tolerance of old-style result objects, diffs for winner/losers/failed/no-winner, migration of a real v1 database, graveyard join both directions, two end-to-end tests through `run_sweep_grid`) |
| `vinu-infra/pipeline_edges.yaml` | modified: one new `wired` edge |

**Tests:** `vinu-research` 1192 -> **1208 passed** (+16); the only failure is the same pre-existing
`test_empty_meanings.py::TestAgentEvalEmptySpelling` (needs `vinu_agent`). The 70 existing sweep/graveyard/generation tests pass
unchanged. Mutation checks: not passing `base_code` fails the end-to-end test; dropping the persisted diff fails 2 tests; both
restored. Edge manifest: 33 edges, 29 wired, 4 known gaps.

**Limits to know:**
- Sweeps written before this change have NULL `base_code_hash` / `code_hash` / diff, so they cannot join (not backfilled).
- The join is on exact code text: any edit to the base code (whitespace included) is a different hash. That is by design
  (`code_hash` is "same code", not "similar idea"); similar-idea matching stays with the TF-IDF dedup in the research loop.

### 2.4d Degraded-run and unfunded-candidate visibility — DONE 2026-10-03 (v1 C4, scoped)

**Scope decision (deviation from v1 C4's proposed solution).** v1 C4 proposed surfacing both facts inside
`GET /research/evaluation-status/by-ticker/{ticker}`. I did not do that. That store is keyed by **artifact id** (research
strategies and trade plans); strategy runs are keyed by **strategy name** (YAML strategies) and daily allocations by strategy
name, and the portfolio container has no mount of the evaluation store, so wiring it would have meant a cross-service write
path plus a deployment change for a fact that changes every day. Instead each fact is made readable where its owner lives.
If you still want them inside evaluation-status, that is a separate, larger decision (new step definition, compose mount).

**Strategy half.** A degraded run (symbols missing required upstream data, or weights clamped/zeroed by the sanity gate) was
visible only in that call's response plus one log line. `evaluate()` now persists `is_degraded`, `degraded_symbols` (capped at 20)
and `sanity_issue_count` on the run row; `GET /strategy/runs` returns it as `metadata`. Also fixed `log_run`, which stored
`str(metadata)` (a Python repr nothing could parse back): new rows are JSON, and rows already holding the old repr are still
read (`literal_eval` fallback; anything unreadable is `{}`, never an error on a read path).

**Portfolio half.** `AllocationHistoryStore` persisted every daily allocation including `not_funded` with a heuristic reason,
and had readers, but no HTTP route anywhere. Added `GET /portfolio/allocation-history` (newest-first summaries with
`n_weights`, `n_not_funded`, equities) and `GET /portfolio/not-funded` (latest allocation's unfunded candidates with reasons;
`status: none` when no allocation was ever recorded, distinct from an empty list when everything was funded).

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-strategy/vinu_strategy/storage/meta.py` | modified: JSON metadata on write, `metadata` on read, `_parse_metadata` |
| `vinu-strategy/vinu_strategy/service.py` | modified: persists the run-quality facts |
| `vinu-portfolio/vinu_portfolio/service.py` | modified: `allocation_history_summaries`, `latest_not_funded` |
| `vinu-portfolio/vinu_portfolio/server/app.py` | modified: the two routes |
| `vinu-strategy/tests/test_run_quality_metadata.py` | **created**, 13 tests (JSON round trip, legacy repr rows, junk metadata, service degraded/clean/sanity/cap) |
| `vinu-portfolio/tests/test_allocation_history_routes.py` | **created**, 7 tests (ordering, limit, none vs empty, reasons, routes, no shadowing) |
| `vinu-infra/pipeline_edges.yaml` | modified: two new `wired` edges |

**Tests:** `vinu-strategy` 137 -> **150** (+13), same 10 pre-existing errors (`ModuleNotFoundError: vinu_portfolio` in the merged-app
and simulator route tests); `vinu-portfolio` 269 -> **276** (+7), no failures. Mutation check: forcing `is_degraded` to always
False fails the degraded-run test; restored. Edge manifest: 35 edges, 31 wired, 4 known gaps.

**Limits to know:**
- Runs before this change have no quality metadata (legacy rows read as `{}`), so "not recorded" and "clean" are different only for
  new rows: look for `is_degraded` being present.
- `not_funded` only exists when `compute_daily_allocation` runs, and per audit A1 nothing in the live path calls it. These routes
  therefore show the last time someone (or the CLI / an agent) ran the allocation, not a live execution decision.

### 2.4e Forecast and refinement prompt inputs — DONE 2026-10-03, partial by design (v1 B3, B4)

Both are opt-in, **off by default**, and with the flag off the prompt is byte-identical to before (asserted by a test). They
change what an LLM sees, and there are no live results yet to say whether the extra context helps, so neither is turned on.

**B3 slice: the forecast LLM now can see the regime and the options-implied move.** The Trade Score and the size multipliers
apply the current market regime and options-implied move right after the forecast, but the forecast prompt never saw either, so
a forecast that ignored them was then scaled against them. With `forecast_prompt_extra_context_enabled`
(`VINU_RESEARCH_FORECAST_PROMPT_EXTRA_CONTEXT_ENABLED`) the regime is fetched **before** the forecast and a "Market Context" section
is shown (regime; options atm_iv / days to expiry only when the snapshot status is ok; the closing sentence names only what is
actually present). The pre-forecast regime result is reused for the sizing multiplier, so there is **no second fetch**
(asserted). A fetch failure leaves the section out and the plan is still produced.

**B4 slice: the refinement LLM can see the rest of the metric row.** It showed Sharpe / MaxDD / win rate / return / trade
count of the ~35-field row its candidate is ranked on. With `refine_prompt_full_metrics_enabled`
(`VINU_RESEARCH_REFINE_PROMPT_FULL_METRICS_ENABLED`) it also gets Sortino, Calmar, CVaR 95, profit factor, win/loss ratio, annual
turnover and the Sharpe 95% CI with p-value, all already computed. The loop marks the generation `story` and the generator reads it.

**Deliberately NOT done (each needs a new data fetch inside authoring/generation, or a policy call):**
synthesis brief, evidence brief and the evaluation-catalog line for the forecast prompt; maturity tier, synthesis, eval catalog,
drawdown events and correlation note for the generation story; per-signal sectioning of the evidence reasoning. They would add
network calls and failure points to authoring for a benefit that cannot be measured yet. Revisit when there are live rows to compare.

**Files touched (inside `vinu-components/vinu-research/`):**

| File | Action |
|---|---|
| `vinu_research/config.py` | modified: two flags + env vars |
| `vinu_research/forecast_skill.py` | modified: `extra_context` through `generate_forecast` and `_build_forecast_prompt` |
| `vinu_research/trade_plan_authoring.py` | modified: pre-forecast regime fetch (reused later), sentinel, `extra_context` passed |
| `vinu_research/llm_generator.py` | modified: `full_metrics` through `_build_refinement_prompt`, `refine`, `_refine_one` |
| `vinu_research/loop.py` | modified: marks the story when the flag is on |
| `tests/test_forecast_extra_context.py` | **created**, 15 tests (byte-identical when off, regime/options rendering, junk context, section order, generate_forecast pass-through, author_trade_plan on/off, no second fetch, fetch failure, empty context leaves the plan unchanged) |
| `tests/test_refinement_full_metrics.py` | **created**, 9 tests (byte-identical when off, real numbers when on, placement, only metric bullets added, generator story path, config/env, loop wiring on/off) |

**Tests:** `vinu-research` 1208 -> **1232 passed** (+24); the only failure is the same pre-existing
`test_empty_meanings.py::TestAgentEvalEmptySpelling` (needs `vinu_agent`). The 196 + 124 existing authoring/forecast/loop/config
tests pass unchanged. Mutation checks, each caught and restored: removing the regime reuse fails the no-second-fetch test; the loop
not marking the story fails the loop-wiring test; the generator ignoring the story flag fails the generator-path test.

### 2.5 Fail-open / fail-closed matrix — DONE 2026-10-03 (v1 C3, doc only)

New file `05-fail-open-fail-closed-matrix.md` in this folder: one table per layer (scheduler path, orchestrator, order boundary,
research/approval) stating, from the code, what each check does when its input is missing, with a file reference per row, plus a
review checklist for new gates. No code changed, no tests added (it describes current behavior).

**It surfaced one new issue, now audit item A7:** a failed broker-equity read sizes the scheduler's orders on an invented
`fallback_portfolio_value` ($1,000,000 by default) instead of aborting the cycle like the portfolio and positions fetches do.
Added to Phase 4 (needs your go-ahead).

| File | Action |
|---|---|
| `newer-thinking-with-discussed/the-inconsistencies-v2/05-fail-open-fail-closed-matrix.md` | **created** |
| `newer-thinking-with-discussed/the-inconsistencies-v2/02-logic-audit-2026-10-02.md` | appended: item A7 |

## Phase 3 — Runtime recorder and "what is not flowing" report — DONE 2026-10-03 (first slice)

**Goal (your idea):** at each point where a component expects something to arrive, record whether it did, so a missing
connection or a stopped service is visible and dated instead of discovered by accident.

**What exists now:**
- **Recorder** (`vinu-infra/pipeline_edge_recorder.py`): `record_edge(edge_id, status, detail)` with status `received | empty |
  stale | missing`. One small state row per edge (latest status, counters, first/last seen, last-ok, last-change) plus a change log
  that only grows when the status **changes** (capped at 200 per edge), so a healthy edge costs a counter bump and no log rows.
  **Never raises, no-op without a configured root, observe-only** (nothing reads it to make a trading decision).
- **Shared root:** `VINU_EDGE_DATA_ROOT`, else the `VINU_STRATEGY_EVAL_DATA_ROOT` that **research-api, live-api and agent-api already
  mount** in docker-compose (`./data/strategy-evaluation:/strategy-eval`), so no compose change was needed. portfolio-api and the
  strategy service do not mount it, so edges consumed there cannot be recorded yet.
- **Manifest extensions:** `instrumented: true` and optional `stale_after_sec` per edge. The static check now also fails
  (`DRIFT_NOT_INSTRUMENTED`) if an edge claims to be instrumented but its consumer never names the edge id in a non-comment line.
- **Instrumented (8 edges, all vinu-live consumers):** `portfolio.state->live.scheduler`, `live_decision.executes->live.scheduler`,
  `strategy.config->live.scheduler`, `maturity.status->live.limits`, `breaker.limits->live.scheduler`, `halt_flag->live.scheduler`,
  `halt_flag->live.orchestrator`, `research.active_trade_plans->live.orchestrator`. Two of them close silent failures: a **non-200
  plan list used to look identical to "no active plans"**, and a failed remote kill-switch read (fail-open) left no trace.
  Stale limits (8000s for the hourly scheduler edges, 1800s for the orchestrator plan list) are set only where the edge fires every
  cycle; event-driven edges (strategy config, breaker, halts) have none because quiet is legitimate for them.
- **Report:** `GET /research/pipeline-edges[?only_problems=true]` joins manifest and recorded state. States: `known_gap`,
  `not_instrumented` (silence says nothing), `never_seen`, `recording_disabled`, `flowing`, `empty`, `stale`, `missing`, each with age,
  counters and the last failure detail. Without a shared root it says `recording_enabled: false` instead of inventing state.

**Behavior change:** none to trading. Recording is a local SQLite write; with no root configured it does nothing.

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-infra/pipeline_edge_recorder.py` | **created**: store, `record_edge`, `edges_flow_report`, `not_flowing` |
| `vinu-infra/pipeline_edges.py` | modified: `instrumented` / `stale_after_sec`, `DRIFT_NOT_INSTRUMENTED` check |
| `vinu-infra/pipeline_edges.yaml` | modified: 8 edges flagged instrumented |
| `vinu-infra/pyproject.toml` | modified: ships `pipeline_edges.yaml` as package data |
| `vinu-infra/tests/test_pipeline_edge_recorder.py` | **created**, 24 tests |
| `vinu-infra/tests/test_pipeline_edges.py` | modified: +5 tests (new manifest fields and the instrumented check) |
| `vinu-live/vinu_live/scheduler.py` | modified: 6 `record_edge` call sites, `edge_id` passed to `halt_reason` |
| `vinu-live/vinu_live/trade_plan/guards.py` | modified: `halt_reason(..., edge_id=None)` records the remote status read |
| `vinu-live/vinu_live/trade_plan/orchestrator.py` | modified: plan-list recording, halt edge id |
| `vinu-live/tests/test_edge_instrumentation.py` | **created**, 14 tests (each edge and status, failures still abort/fail-open exactly as before, a broken or absent recorder changes nothing) |
| `vinu-research/vinu_research/server/routes_introspect.py` | modified: `GET /research/pipeline-edges` |
| `vinu-research/tests/test_routes_introspect_pipeline_edges.py` | **created**, 7 tests |

**Tests:** `vinu-infra` 368 -> **397** (+29); `vinu-live` 637 -> **651** (+14), same 3 pre-existing errors; `vinu-research` 1232 ->
**1239 passed** (+7), with two failures that are both pre-existing: `test_empty_meanings.py::TestAgentEvalEmptySpelling` (needs
`vinu_agent`) and `test_sqlite_backend.py::TestThreadSafety::test_concurrent_writes`, a **flaky** "database is locked" concurrency
test (verified: with every vinu-research change stashed it fails 6/6; intermittent passes seen otherwise; unrelated to this work).
Mutation checks: letting a recorder exception escape fails the "broken recorder changes nothing" test (it would otherwise have failed a
real trading cycle); dropping the non-200 plan-list recording fails its test; both restored.

**Limits to know:**
- **Only 8 of 31 wired edges are instrumented**, all on the vinu-live consumer side. The agent, portfolio, strategy, reflection and
  research consumers are still `not_instrumented`. Extending is mechanical (one `record_edge` call + `instrumented: true`), and the
  static check will tell you if the id is missing.
- It reports **presence and age, not correctness**: a stale-but-present or wrong value still reads as `received`.
- A `known_gap` edge is not checked at runtime; that is the static check's job.
- The report is only as good as the recording root: if the shared mount is absent in a deployment the route says so.

## Phase 5 — New safeguards

### 5.1 (features) and 5.2: look-ahead and warmup-drift checks — DONE 2026-10-03

**What was built:** `vinu-tools/vinu_tools/compute/bias_checks.py`, two pure offline checks over the real feature registry:
- `lookahead_report`: computes each feature on the full series and on several prefixes, and flags any value at bar t that changes when the
  future is removed. It also reports `unverifiable` features (no value at any checked bar), because comparing None with None proves nothing.
- `warmup_drift`: relative difference at the newest bar between a short trailing window (what the live poller sees) and full history (what a
  backtest sees). Cumulative-from-start features are named in `CUMULATIVE_FEATURES`.
Deterministic synthetic OHLCV by default, so results are reproducible. Limit: it proves "no leak found on this path", not "no leak possible"
(a leak that does not change a value at the sampled cuts is invisible), and it says nothing about whether a value is correct.

**Results over all 651 registered single features:** **no look-ahead found.** But building the check exposed two real bugs that had made
whole feature families silently dead; both are now fixed:

| # | Bug found | Effect | Fix |
|---|---|---|---|
| 1 | The alpha evaluator's `ref` indexed a dict with a numpy array (`Ref($close, 5)` is rewritten to `ref(close, 5)` where `close` is already the array); the `TypeError` was swallowed by a blanket `except` in `evaluate` | Every `Ref(...)`-based factor returned an all-None column: **354 of 360 alpha360, 64 of 158 alpha158, 25 of 101 alpha101** columns | One line in `evaluator.py`: accept the array or the name. Now 360/360, 158/158, 101/101 columns have values; the lag is verified correct. |
| 2 | `expand_features` lowercases names but `_alpha_name_sets()` holds UPPERCASE names, so a single alpha requested by name (`ALPHA101_001`, `BETA10`, `CLOSE1`) matched no case-sensitive branch | `validate_feature_name` said valid, `apply_indicators` silently added **no column**, `warmup_bars_for_features` said **1 bar instead of 60** | `_canonical_alpha_names` restores catalog case in `apply_indicators` and `warmup_bars_for_features`. Whole-recipe requests and every non-alpha indicator are unchanged. |

**Behavior change to know about:** features that used to be silently None (the alpha families above) now carry real values wherever they are
requested. Nothing in the live detector requests them (its list is the 43 base indicators), but any strategy or tool that did request an alpha
feature was getting nothing and will now get numbers. The blanket `except` in `evaluate` is unchanged on purpose (a bad expression is still a None
column, not a crash); the new registry test fails if any column is ever all-None again.

**Measured live-vs-backtest drift (the audit's A2 question), at the live detector's real window of 201 bars:** most indicators are identical to
backtest. The exceptions, all now pinned by a ratcheting budget test:
- `ema_200`: up to **~4.5%** off backtest (worst of several random paths); `ema_100` up to ~0.4%; `ema_50` ~3e-5. An EMA needs several times its period
  to converge; "warmup bars" in the registry means "first non-None value", not "converged". A must-condition on `ema_200` can therefore evaluate
  differently live than in backtest near its boundary.
- `supertrend` up to ~11% (path dependent). MACD, MACD signal, ADX, RSI, ATR are all below ~1e-4.
- `obv`, `accumulation_distribution_line`, `vwap` are **cumulative from the first bar**, so their absolute LEVEL differs enormously (tens of percent to
  several hundred percent) between a window and history; only their changes are meaningful. Pinned as known level-dependent.

**Decision recorded for Phase 4 (audit A8):** enlarge the live window so slow EMAs converge (about 3x the longest EMA period, ~600 bars), or
stop using absolute `ema_100` / `ema_200` / `obv` levels in live must-conditions. Changing the window changes live snapshot values toward
backtest (more accurate), costs a larger bars fetch per poll, and needs your go-ahead because it changes live decisions. The pin test below makes
sure the budgets are re-measured if the window is ever changed.

**Files touched (inside `vinu-components/`):**

| File | Action |
|---|---|
| `vinu-tools/vinu_tools/compute/bias_checks.py` | **created** |
| `vinu-tools/vinu_tools/compute/registry.py` | modified: `_canonical_alpha_names`, used in `apply_indicators` and `warmup_bars_for_features` |
| `vinu-tools/vinu_tools/compute/factors/recipes/_alpha_expr/evaluator.py` | modified: the one-line `ref` fix (with an explanatory comment) |
| `vinu-tools/tests/test_bias_checks.py` | **created**, 27 tests (harness catches a leak / a global-normalisation leak / none-to-value; unverifiable is not clean; registry-wide no look-ahead and none dead; ratcheting drift budgets over 3 seeds; cumulative features pinned; bug 1 and bug 2 regressions) |
| `vinu-live/tests/test_live_window_pinned.py` | **created**, 2 tests pinning the live window (201) and feature list the budgets were measured for |

**Tests:** `vinu-tools` 177 -> **204** (+27); `vinu-live` 651 -> **653** (+2), same 3 pre-existing errors. `vinu-stock-price` indicator tests (16) and the live
detector tests (17) pass unchanged. Mutation checks, each caught and restored: reintroducing the `ref` bug fails 7 tests; reverting the name fix in
`apply_indicators` fails 9; reverting it in `warmup_bars_for_features` fails 1.

**Still open in Phase 5.1:** the strategy-level look-ahead test (running whole strategies or `simulate_custom` code on truncated data). Features come first
because they are cheap and are what strategies are built from; whole strategies need a decision on the cut points and cost per run.

---

## Phase 4 — decisions (all made; nothing is waiting on you)

These were open questions. They are now decided and built, so they no longer wait on an answer. Reversible by flag.

1. **A2 (overlap of trade-plan and portfolio symbols):** not knowable from code, so the rule is safe whether or not they overlap. A symbol is the orchestrator's if it has
   an open book position or an ACTIVE trade plan; the orchestrator is the single sizing authority for it (the scheduler drops it from targets and positions).
2. **A1 (which allocation the scheduler uses):** decided -- option A, `/portfolio/daily-allocation`, weights scaled by deployable / account equity, falling back to
   `/portfolio/state` on failure.
3. **Positions nothing targets any more (the question I kept asking):** decided -- the scheduler closes such a position **only if it opened it** (the order ledger shows an
   accepted BUY, or the symbol is listed in `scheduler_adopted_symbols`) and the orchestrator does not own it and ownership is known. Anything else held with no target
   (a hand-placed holding, or an unidentifiable one) is left alone. Built 2026-10-03, see "A2 follow-up" below.
4. **A7:** decided and built -- a failed read of a configured broker's equity aborts the cycle; the $1M placeholder is used only for `configured: false`.
5. **Paper-to-real-money date:** not a code decision. `06-live-behavior-flags.md` gives the order in which to switch the flags on; real money waits until they have run on paper.

---

## Log

- **2026-10-02** — Phase 1 completed. `vinu-infra` suite 350 → 368 passed. No existing file modified; nothing committed.
- **2026-10-02** — Phase 2.1 completed. `vinu-research` suite 1185 → 1192 passed (+7), same 1 pre-existing failure. Nothing committed.
- **2026-10-02** — Phase 2.2 completed. `vinu-live` 577 → 599 passed (+22), same 3 pre-existing errors; edge manifest 24 wired / 4 gaps. Flag off by default. Nothing committed.
- **2026-10-03** — Phase 2.3 completed. `vinu-live` 599 → 621, `vinu-strategy` 131 → 137, `vinu-infra` 368; edge manifest 26 wired / 4 gaps. Nothing committed.
- **2026-10-03** — Phase 2.4a/2.4b completed (stuck live-decision triggers fixed, needs-sizing queue). `vinu-live` 621 → 637; edge manifest 28 wired / 4 gaps. Nothing committed.
- **2026-10-03** — Phase 2.4c completed (`code_hash` join, persisted `param_diff`). `vinu-research` 1192 → 1208; edge manifest 29 wired / 4 gaps. Nothing committed.
- **2026-10-03** — Phase 2.4d completed (run-quality persisted, allocation-history routes). `vinu-strategy` 137 → 150, `vinu-portfolio` 269 → 276; edge manifest 31 wired / 4 gaps. Nothing committed.
- **2026-10-03** — Phase 2.4e completed (forecast + refinement prompt slices, opt-in). `vinu-research` 1208 → 1232. Phase 2 now complete except the C3 matrix doc. Nothing committed.
- **2026-10-03** — Phase 2.5 completed (fail-open/closed matrix; found audit A7). **Phase 2 is complete.** Nothing committed.
- **2026-10-03** — Phase 3 completed (first slice). `vinu-infra` 368 → 397, `vinu-live` 637 → 651, `vinu-research` 1232 → 1239 passed (2 pre-existing failures, one flaky). Edge recorder + `GET /research/pipeline-edges`; 8 of 31 wired edges instrumented. Nothing committed.
- **2026-10-03** — Phase 5.1 (features) + 5.2 completed: bias_checks module; found and fixed two registry bugs that had silently killed the alpha factor families; quantified live-window drift (EMA-200 up to ~4.5%). `vinu-tools` 177 -> 204, `vinu-live` 651 -> 653. Nothing committed.

- **2026-10-03** — Files renamed with number prefixes (01-..05-). Convention: when every point in a list file is fixed, its name gets a `(comp)-` prefix, e.g. `(comp)-01-inconsistencies-v2.md`. None are complete yet (A1, A2, A5, A6, A7, A8, v1 A8, B1 still open).

## Phase 4 — Decisions that change live behavior (started 2026-10-03 on your "ok proceed")

### A7: a failed broker-equity read no longer sizes orders on $1,000,000 — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** `LiveConfig.abort_on_equity_read_failure` (env `VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE`, default false). When on,
`LiveScheduler._fetch_portfolio_value` raises (the cycle is marked `failed`, no orders) if the account read FAILED: exception, non-200, a
`configured: true` reply with no usable equity, or a reply that is not a dict. Only an explicit `configured: false` (no broker at all) still
uses "positions x price" / `fallback_portfolio_value`, as before. Off = old behavior exactly.

**Deliberately not changed:** the trade-plan orchestrator's own `_fetch_portfolio_value` keeps its fallback, because the orchestrator sizes
EXITS from the same value and aborting there would block a reduce. (Its fallback is still an invented figure; fixing it safely means
separating "equity for sizing entries" from "equity for exits" -- a separate decision, noted here, not started.) On the scheduler path an abort
also pauses exits for that hour, the same as the existing positions / portfolio fetch failures.

**To turn it on:** set `VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE=true` for the live service. Recommended once you are on a configured Alpaca account.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/config.py` | modified: flag + env |
| `vinu-live/vinu_live/scheduler.py` | modified: `_fetch_portfolio_value` distinguishes failed read from `configured: false` |
| `vinu-live/tests/test_scheduler_equity_abort.py` | **created**, 10 tests (4 failure shapes abort when on; old fallback when off; `configured:false` never aborts; good read unchanged; whole cycle fails and posts no order; flag default/env) |

**Tests:** `vinu-live` 653 -> **663** (+10), same 3 pre-existing errors. Mutation check: removing the abort fails 5 of the 10 tests; restored.

- **2026-10-03** — Phase 4 started: A7 done (opt-in). `vinu-live` 653 -> 663. Nothing committed.

### A8: configurable live feature window (slow EMAs converge) — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** `LiveConfig.live_decision_feature_window_bars` (env `VINU_LIVE_DECISION_FEATURE_WINDOW_BARS`, default 0 = old 201-bar window).
When > 0 the live-decision poller fetches `max(minimum warmup, this)` bars (`detector.feature_window_bars`); a too-small value can never shrink
the window below the warmup. **Measured live-vs-backtest drift at the newest bar (worst of 5 random paths):**

| window | ema_200 | ema_100 | ema_50 | supertrend |
|---|---|---|---|---|
| 201 (today) | 4.2% | 0.42% | 5e-5 | ~11% |
| 400 | 0.21% | 2e-3% | ~0 | 14% |
| **600 (recommended)** | **0.055%** | 9e-5% | ~0 | 14% |
| 800 | 0.005% | ~0 | ~0 | 14% |

**Honest limits:** (1) `supertrend` does **not** improve with a longer window -- its error is flip-state path dependence, not warmup, so a
must-condition on supertrend can still differ live vs backtest. (2) `obv`, `accumulation_distribution_line`, `vwap` are cumulative from the first
bar; a longer window changes their level but never makes it equal to a backtest's -- use their changes, not their levels. (3) Costs a bigger
bars fetch per new candle (600 vs 201 rows per ticker/timeframe pair). (4) The scheduler path does not use these snapshots; only the poller does.
(5) The poller's pinned-window test and the drift budgets in `test_bias_checks.py` still describe the default 201; the 600 case has its own test.

**To turn it on:** `VINU_LIVE_DECISION_FEATURE_WINDOW_BARS=600`. Changes live snapshot values toward backtest, so a strategy tuned on the old
live numbers may fire at slightly different moments.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/config.py` | modified: flag + env |
| `vinu-live/vinu_live/live_decision/detector.py` | modified: `feature_window_bars()` |
| `vinu-live/vinu_live/live_decision/poller.py` | modified: fetch limit uses it |
| `vinu-live/tests/test_live_feature_window.py` | **created**, 5 tests (flag/env, never below minimum, default fetches minimum, configured 400/600 fetched) |
| `vinu-tools/tests/test_bias_checks.py` | modified: +3 tests (600-bar window converges ema_200 within 0.2%, strictly better than 201) |

**Tests:** `vinu-live` 663 -> **668**, `vinu-tools` 204 -> **207**; same 3 pre-existing vinu-live errors. Mutation check: poller back to the
minimum window fails the 2 configured-window tests; restored.

- **2026-10-03** — Phase 4: A8 done (opt-in live feature window). `vinu-live` 663 -> 668, `vinu-tools` 204 -> 207. Nothing committed.

### A5: exits no longer trapped by halts and gates on the scheduler path — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** `LiveConfig.scheduler_exits_exempt_from_halts` (env `VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS`, default false). When on:
- `OrderInstruction.reduces_exposure` / `ExecutionSlice.reduce_only` (both default False; TWAP and VWAP planners carry the flag onto every slice).
  The scheduler tags an instruction as reducing with the existing `instruction_increases_exposure` helper (the same one the A4 entry guards use),
  so a sell that would flip long into short is NOT treated as a reduce.
- **Breaker HALT:** still blocks new exposure, but the cycle now also executes the reducing instructions (`result["exits_only"] = True`,
  status stays `halted_by_breaker`).
- **Kill switch / remote halt in `_execute_plan`:** only reducing slices run; increases are dropped. A halt that appears *mid-plan* drops the
  remaining increases but keeps the remaining exits (before, it broke out of the whole plan).
- **Spread gate and event blackout:** skipped for reducing slices only, and a reducing slice always goes as a **market** order (a passive limit
  could rest unfilled and trap the position). Wide-spread / blackout entries are still skipped exactly as before.
- Reducing orders are posted with `reduce_only: true`, so the agent-side OrderGuard applies its existing reduce-only exemptions.
Off = every code path is unchanged (no tag, no `reduce_only` in the payload, halt still stops everything).

**Limits / things to know:**
- The agent-side OrderGuard still decides whether a reduce-only order passes a halt (`_halt_policy_allows_reduce_only`); this change makes the
  scheduler *send* the order, it does not override that policy.
- Market exits in a wide spread cost slippage; that is the deliberate trade for never being trapped.
- Does not change the trade-plan orchestrator (it already behaved this way).
- A5 only decides *whether the order is sent*; exits are still sized by the scheduler's target weights (so A1/A2 questions about which weights are
  right are unchanged).
- The manifest edge `order.reduce_only->live.scheduler` flipped from `gap` to `wired` (the static check forced it): vinu-infra manifest is now
  **32 wired, 3 known gaps**. It is wired in code but live only with the flag on.

**To turn it on:** `VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS=true`. Recommended before real money.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/config.py` | modified: flag + env |
| `vinu-live/vinu_live/signal_translator.py` | modified: `OrderInstruction.reduces_exposure` |
| `vinu-live/vinu_live/execution.py` | modified: `ExecutionSlice.reduce_only`, carried by `plan_twap` / `plan_vwap` |
| `vinu-live/vinu_live/scheduler.py` | modified: tagging, breaker-HALT exits, `_execute_plan` halt / mid-plan / gate / order-type / payload |
| `vinu-infra/pipeline_edges.yaml` | modified: edge flipped gap -> wired |
| `vinu-live/tests/test_scheduler_exits_exempt.py` | **created**, 17 tests (flag/env; planners carry the flag; halt blocks all when off; exits pass a halt and increases do not; mid-plan halt both modes; spread and event gates per side; market not limit; `reduce_only` only when on; whole-cycle breaker HALT both modes) |

**Tests:** `vinu-live` 668 -> **685** (+17), same 3 pre-existing errors; `vinu-infra` 397 unchanged (one edge test forced the manifest flip).
Mutation checks (each restored): removing the gate exemption fails 2; dropping the `reduce_only` payload fails 2; dropping the mid-plan exemption
fails 1; dropping the breaker-HALT exits fails 1. Removing the early halt filter alone does **not** fail a test: it is redundant with the per-slice
skip (same behavior), kept as a clear early return.

- **2026-10-03** — Phase 4: A5 done (opt-in exits exempt from halts). `vinu-live` 668 -> 685; edge manifest now 32 wired / 3 gaps. Nothing committed.

### A1 + A2: the allocation contract and executor symbol ownership — DONE 2026-10-03 (both opt-in, default OFF)

**A1 — what was built:** `LiveConfig.scheduler_use_daily_allocation` (env `VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION`). When on, `LiveScheduler._fetch_portfolio`
reads `/portfolio/daily-allocation` (chosen contract: "Option A" of the audit) and multiplies each tilted weight by
`deployable_equity / account_equity`, clamped to [0, 1] (1.0 when either figure is missing). That is the one place the drawdown ladder
(`ok` 1 / `halve` 0.5 / `flat` and `halt` 0), the maturity capital ladder and the reserve fraction act: they scale TOTAL capital, not the relative
weights, so they could never show up in the weights themselves. The cycle result carries `allocation_source` and `deployable_fraction`. If
daily-allocation cannot be read, the scheduler falls back to `/portfolio/state` (today's behavior) and says so (no `allocation_source`);
`status != ok` / no weights yields no weights (no fallback). Live-decision weights are added afterwards and are never scaled.
Consequences to know: (1) drawdown `flat` / `halt` now means the scheduler asks for NO portfolio positions, i.e. it sells the book down
(intended "exit to flat"; pair it with `scheduler_exits_exempt_from_halts` so the sells are not blocked); (2) calling daily-allocation hourly writes
its dated history row and updates the portfolio service's in-memory hysteresis memory each time (its own docstring already allows any cadence);
(3) while on, `/portfolio/state` is read only as the fallback, so its edge shows as idle in the runtime report (expected).

**A2 — what was built:** `LiveConfig.scheduler_respect_trade_plan_symbols` (env `VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS`). When on, a symbol is
orchestrator-owned if it has an OPEN position in the trade-plan book or an ACTIVE `trade_plan` artifact (the research API, two-step read). The scheduler
then drops that symbol from both its targets and the positions its translator sees, so it neither sizes nor sells it (the orchestrator stays the single
sizing authority; the cycle result reports `ownership.targets_skipped_orchestrator_owned` / `positions_left_alone`). If ownership cannot be read
(research API down, a plan unreadable) it additionally leaves every held position with no target this cycle alone (`ownership_unknown`) rather than
guessing. The helper never raises; any failure leaves the inputs untouched.

**NEW FINDING while testing A2 (corrects the audit's A2 premise):** `LiveScheduler._fetch_prices(target_weights)` prices ONLY symbols that have a target,
so `SignalTranslator` skips every held-but-untargeted position with "No usable price ... will retry next cycle once priced" -- it is never priced, so it is
never sold. Two consequences: (a) the audit's "scheduler liquidates the orchestrator's untargeted positions" hazard is currently MASKED by this bug,
not absent; the live hazard today is the OVERLAP case (a symbol in both lists is sized by both authorities), which A2 does fix; (b) the translator's
docstring promise that a dropped strategy's symbol is closed is false in practice -- orphaned positions of retired strategies are never exited.
I deliberately did NOT fix the pricing: doing so would make the scheduler liquidate EVERYTHING in the account it has no target for, including any
holding you placed by hand in Alpaca. Decided afterwards: see "A2 follow-up". It is pinned by `test_known_finding_...` so that the day pricing
changes, the test flips on purpose and the ownership guard is already in place.

**To turn them on:** `VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION=true` and `VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS=true`.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/config.py` | modified: two flags + env |
| `vinu-live/vinu_live/scheduler.py` | modified: `_fetch_daily_allocation`, `_fetch_trade_plan_symbols`, `_apply_symbol_ownership`, hooks in `_fetch_portfolio` and `cycle` (+ `import json`) |
| `vinu-infra/pipeline_edges.yaml` | modified: `portfolio.daily_allocation->live.scheduler` gap -> wired + instrumented |
| `vinu-live/tests/test_scheduler_allocation_and_ownership.py` | **created**, 21 tests (flags/env; state-only when off; halve/flat/clamp/missing figures; fallback; empty; whole cycle halves the order, flat sells; ownership via book / via active plan / both lists / unknown plans / failure-safe; the pricing finding pinned) |

**Tests:** `vinu-live` 685 -> **706** (+21), same 3 pre-existing errors; `vinu-infra` 397 unchanged. Edge manifest: **33 wired, 2 known gaps**
(`book.writes->scheduler`, `precondition_held->scheduler`). Mutation checks (each restored): removing the scaling fails 4; removing the fallback fails 1;
not dropping owned targets fails 1; not holding untargeted positions when ownership is unknown fails 1; not removing owned positions fails 1.

- **2026-10-03** — Phase 4: A1 + A2 done (opt-in); new finding: held-but-untargeted positions are never priced so never sold. `vinu-live` 685 -> 706; edge manifest 33 wired / 2 gaps. Nothing committed.

### A6: the scheduler's breaker reads the broker account — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** `LiveConfig.scheduler_breaker_uses_broker_account` (env `VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT`). When on:
- **Positions:** the breaker's position-count, leverage and cluster checks run over the live BROKER positions (the whole account, taken before the A2
  ownership filter) instead of the trade-plan book's open positions. `check_limits` gained an optional `positions=` argument (None = read the book, every
  other caller unchanged); shorts are passed as `side="short"` with the absolute quantity so gross exposure counts them.
- **Daily loss:** `equity now - the first equity this scheduler saw today (UTC)`, so an open drawdown counts, not only closed trades. The baseline is kept in
  `<data_root>/breaker_day_equity.json` (survives a restart, resets on a new UTC date). Only used when the equity came from a real broker read
  (`_equity_is_real`); a placeholder equity never creates a baseline.
- Anything it cannot obtain falls back to the old inputs (no broker positions passed -> book; unreadable baseline file -> realized book P&L). It never raises.
Off = the breaker call and inputs are exactly as before.

**Limits / things to know:**
- **It can newly HALT trading** (the reason it is opt-in): an account that already holds more than 20 positions, or runs above 2x leverage, or is down
  more than 5% on the day, now halts the scheduler path (and engages the real kill switch, like any breaker halt).
- The baseline is the first equity this process saw that UTC day, not the prior close or the market open; a scheduler that starts mid-day after a loss
  measures from there. (The broker route does not expose `last_equity`; adding it would be a better baseline and is a small follow-up.)
- The engine divides the loss by CURRENT equity (7,000 / 93,000 = 7.5%), which trips slightly earlier than dividing by the baseline.
- The scheduler still writes nothing to the plan book (edge `book.writes->live.scheduler` stays a known gap); this change bypasses the book rather than
  filling it. Aggregate-VaR is still skipped on this path (no covariance matrix), as before.
- The orchestrator's own breaker is unchanged.

**To turn it on:** `VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT=true`.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/breaker/engine.py` | modified: `check_limits(..., positions=None)` |
| `vinu-live/vinu_live/config.py` | modified: flag + env |
| `vinu-live/vinu_live/scheduler.py` | modified: `_account_daily_pnl`, `_check_breaker(portfolio_value, broker_positions=None)`, `_equity_is_real`, cycle passes the unfiltered broker positions when on |
| `vinu-live/tests/test_scheduler_breaker_broker_inputs.py` | **created**, 15 tests (flag/env; explicit positions override the book; blind when off; count, leverage incl. shorts; unrealized drop trips; off ignores it; small move / gain allowed; baseline survives restart; new day resets; placeholder equity makes no baseline; broken file falls back; whole cycle both modes) |

**Tests:** `vinu-live` 706 -> **721** (+15), same 3 pre-existing errors; `vinu-infra` 397 unchanged. Mutation checks (each restored): ignoring the explicit
positions fails 2; ignoring the account P&L fails 3; allowing a placeholder equity fails 1; ignoring the flag fails 3.

- **2026-10-03** — Phase 4: A6 done (opt-in broker-sourced breaker inputs). `vinu-live` 706 -> 721. Nothing committed.

### v1 A8: precondition enforcement — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** `LiveConfig.precondition_enforcing_enabled` (env `VINU_LIVE_PRECONDITION_ENFORCING_ENABLED`, default false). When on,
`LiveScheduler._fetch_live_decision_weights` refuses an unapplied live-decision EXECUTE whose `precondition_held` is **False**: no position is opened for it,
the decision is marked applied (final information, like an unsized EXECUTE -- it is not retried), a warning is logged, and the cycle result carries
`precondition_blocked: [{ticker, strategy_id, decision_id, bar_ts}]` (also present when the cycle then skips for no weights). `precondition_held` of
True or None (unknown) still passes -- fail-open, so a missing flag can never block. Positions already open are untouched, and the portfolio-weight
path is not affected. Off = identical to before.

**Limits:** it uses the flag as the agent stated it; it does not verify the claim. It only gates opening a position (the point at which an EXECUTE
becomes an order), not the poller's own EXECUTE record, which keeps its `precondition_held` value for reflection. `tested` (the other half of the v1
description) is not enforced -- only `precondition_held` was the scheduler-readable field. The refusal is visible in the cycle result and logs, but
it is not written to a separate table; the decision row itself (applied, with `precondition_held = 0` and no open position) is the durable record.

**To turn it on:** `VINU_LIVE_PRECONDITION_ENFORCING_ENABLED=true`.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/config.py` | modified: flag + env |
| `vinu-live/vinu_live/scheduler.py` | modified: gate in `_fetch_live_decision_weights`, `_precondition_blocked`, `precondition_blocked` in the cycle result |
| `vinu-infra/pipeline_edges.yaml` | modified: `precondition_held->live.scheduler` gap -> wired (forced by the static check) |
| `vinu-live/tests/test_scheduler_precondition_gate.py` | **created**, 8 tests (flag/env; false -> no position and no order; refusal is final; true / unknown still trade; off unchanged; one of two; open position untouched) |

**Tests:** `vinu-live` 721 -> **729** (+8), same 3 pre-existing errors; `vinu-infra` 397. Edge manifest now **34 wired, 1 known gap**
(`book.writes->live.scheduler`). Mutation checks (each restored): gate removed fails 3; None blocked too fails 1; refused decision not marked applied fails 1;
flag ignored fails 1.

- **2026-10-03** — Phase 4: v1 A8 done (opt-in precondition gate). `vinu-live` 721 -> 729; edge manifest 34 wired / 1 gap. Nothing committed.

### B1: confidence recalibration — DONE 2026-10-03 (log-only ON; using it OFF)

**What was built:** `vinu-research/vinu_research/confidence_calibration.py` (pure) learns what the forecast LLM's stated confidence has actually meant.
- **Recovering the stated confidence.** `calibration_entries` does not store it, but it stores the Brier score and whether the call was right, and
  `compute_brier_score` is `(confidence - hit)^2` for long / short calls, so `confidence = 1 - sqrt(brier)` for a hit and `sqrt(brier)` for a miss
  (verified round-trip over 16 direction / outcome / confidence combinations). Neutral calls and corrupt rows are skipped. No schema change.
- **The map:** 10 fixed buckets over [0, 1], pooled over every closed trade (`SqliteStrategyStore.list_all_calibration_entries`, newest 5,000).
  A bucket below `confidence_calibration_min_samples` (default 30) is NOT trusted: the raw confidence is returned. A trusted bucket's hit rate is shrunk
  toward the raw confidence by that many pseudo-trades, so a bucket that has just crossed the floor cannot swing a score on a handful of trades.
- **Three flags (research service, env in brackets):**
  1. `confidence_reliability_log_enabled` (default **ON**, no behavior change) -- every newly authored plan gets one `trade_score.reasons` line, e.g.
     `calibrated_confidence=0.59 (raw=0.90; bucket n=100, realized hit-rate=0.50); log-only, EV uses raw`. The database is only read if it already exists
     (never created by this), and any failure is swallowed. [`VINU_RESEARCH_CONFIDENCE_RELIABILITY_LOG_ENABLED`]
  2. `calibrated_confidence_in_ev_enabled` (default **OFF**) -- the Trade Score's EV term uses the calibrated number instead of the raw one.
     [`VINU_RESEARCH_CALIBRATED_CONFIDENCE_IN_EV_ENABLED`]
  3. `confluence_excludes_forecast_confidence` (default **OFF**) -- drops the `forecast_confidence` vote from the confluence ledger, so the same LLM number
     is not counted a second time as independent evidence. [`VINU_RESEARCH_CONFLUENCE_EXCLUDES_FORECAST_CONFIDENCE`]
  Plus `confidence_calibration_min_samples` [`VINU_RESEARCH_CONFIDENCE_CALIBRATION_MIN_SAMPLES`].
- `compute_trade_score` / `check_trade_score_gate` gained keyword-only `ev_confidence` and `confluence_exclude_signals` (defaults leave every other caller identical).

**Limits / things to know:**
- **It is inert until there is data.** No bucket reaches 30 closed trades until a lot of plans have closed, so for now the log line will say
  `raw_no_map` / `raw_insufficient_sample` and nothing changes even with flag 2 on. That is the intended "log-only first".
- The third use of the raw number -- the size scale (tier multiplier and the orchestrator's 0.5-floor confidence scale) -- is NOT changed. The tier
  moves indirectly when EV or confluence move; the orchestrator's own `confidence` scale is a separate decision.
- Pooled across all strategies and symbols; a per-regime or per-strategy map would need far more trades per bucket.
- Plans are scored at authoring time; changing a flag does not rescore plans already frozen or ACTIVE.
- Adds one line to `trade_score.reasons` on every new plan while flag 1 is on.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-research/vinu_research/confidence_calibration.py` | **created** (pure map / recover / calibrate) |
| `vinu-research/vinu_research/storage/strategy_store.py` | modified: `list_all_calibration_entries` |
| `vinu-research/vinu_research/gates/trade_score_gate.py` | modified: `ev_confidence`, `confluence_exclude_signals` |
| `vinu-research/vinu_research/trade_plan_authoring.py` | modified: builds the map, passes the two options, appends the evidence line |
| `vinu-research/vinu_research/config.py` | modified: 4 fields + env |
| `vinu-research/tests/test_confidence_calibration.py` | **created**, 40 tests (round-trip recovery, neutral/corrupt skipped, buckets, floor, shrinkage both directions, invalid input, gate parameters, flags/env, real `author_trade_plan` against a seeded store: log-only leaves score unchanged, in-EV lowers an overconfident score, too little history changes nothing, no DB is created, a broken DB never breaks authoring, confluence flag) |
| `vinu-research/tests/test_routes_introspect_pipeline_edges.py` | modified: its "known gap" example edge moved to `book.writes->live.scheduler` (the previous example was wired by A1) |

**Tests:** `vinu-research` 1239 -> **1278** passed (+40 new; the 2 failures are the same pre-existing `test_empty_meanings` and the flaky `test_sqlite_backend` concurrency
test); vinu-agent trade-plan tests 71 pass; `vinu-infra` 397. Mutation checks (each restored): in-EV flag ignored fails 1; sample floor ignored fails 5;
recovery formula flipped fails 18; confluence exclusion ignored fails 2; shrinkage removed fails 1; EV forced back to raw fails 2.

**Phase 4 is now complete:** A5, A7, A8, A1, A2, A6, v1 A8, B1 are all built as opt-in flags (B1's log line is on by default and harmless). None of the live-behavior
flags is switched on anywhere; turning them on is an operations decision (see `06-live-behavior-flags.md` for every flag, its env var and a suggested order).

- **2026-10-03** — Phase 4 complete: B1 done (log-only on, use off). `vinu-research` +40 tests. Nothing committed.

### 5.3: backtest-vs-realized parity report (v2 A3) — DONE 2026-10-03 (read-only, advisory)

**What was built:** `vinu-research/vinu_research/parity_report.py` (pure) and `GET /research/parity-report?min_days=20&min_trades=30`.
Two comparisons:
1. **Strategies, backtest vs paper replay.** For each strategy artifact in BENCHING / ACTIVE / MONITORING / DECAYED: the backtest's `initial_sharpe` and
   `initial_max_dd` against realized Sharpe, max drawdown and hit rate over its paper days. The Sharpe comparison carries a **standard error** (Lo 2002,
   i.i.d. approximation), a z-score, and `detectable_shortfall` (2 SE: a smaller gap could not have been seen). Verdicts: `insufficient_data` (< 20 days),
   `no_backtest_expectation` (no positive backtest Sharpe), `in_line`, `underperforming` (z < -2). `drawdown_exceeds_backtest` is a separate flag (realized
   max DD > 1.5x the backtest's). When `in_line` rests on a window so short that the smallest detectable shortfall exceeds the whole expected Sharpe, the row says
   "weak evidence" in its note instead of passing quietly.
2. **Trade plans, stated vs realized** (closed live trades, `calibration_entries`, pooled): mean stated confidence (recovered from the Brier score, see B1) vs
   realized hit rate with a binomial z; mean forecast magnitude vs mean realized move in the forecast direction. Verdicts: `insufficient_data` (< 30 trades),
   `overconfident` (z < -2), `overstated_magnitude` (< 50% of the forecast move captured), `in_line`.
Paper days are read from vinu-agent's `paper_performance.db` when `agent_data_root` is mounted on the research service, else from the agent API
(`/agent/broker/performance/{id}`); the response says which (`paper_source`: `db` / `agent_api` / `unavailable`). Read-only; no flag; nothing consumes the verdicts.

**IMPORTANT finding that changes what "paper vs backtest" can mean (corrects the v2 A3 premise):** the paper series is NOT independent of the backtest engine.
`ShadowEvaluator.record_daily_paper_returns` asks research for "the most recent trading day's return its `strategy_code` would have produced" and appends that.
It is the same code re-run on one new day: no order, no fill, no spread, no slippage. So this report measures **out-of-sample stability after promotion** (did the
edge survive new days?), not **execution parity**. The report's own `caveat` field says so. Real execution parity (live fill vs the reference price at decision
time, trade frequency vs backtest) needs data this system does not record: the book keeps fills but not the decision-time reference price, and the scheduler path
writes no fills to the book at all (edge `book.writes->live.scheduler`). That remains open (see "still open" below).

**Not done:** writing the verdict as a `reflection_beliefs` row / `strategy_evaluation_history` step, surfacing it in `get_live_decision_context`, and letting a
parity pass gate the `mature` tier or promotion. All of those are consumers, i.e. decisions; the report exists first so they have something real to read.
Per-artifact trade-plan parity is also not done (pooled only: per-artifact buckets would be far too thin).

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-research/vinu_research/parity_report.py` | **created** (realized stats, Sharpe SE, strategy parity, trade-plan parity, report builder, read-only `paper_performance.db` reader) |
| `vinu-research/vinu_research/server/routes_introspect.py` | modified: `GET /research/parity-report` |
| `vinu-research/tests/test_parity_report.py` | **created**, 21 tests (known-number stats, junk-robust, SE formula, too-few-days, no expectation, in line / underperforming / thin-window note, drawdown flag, trade-plan insufficient / overconfident / calibrated / magnitude / short sign / junk, report builder, DB reader round trip and failures, route joins, route parameters, route without paper data, empty system) |

**Tests:** `vinu-research` 1278 -> **1300** passed (+21 new, plus the flaky concurrency test passing this run); the one failure is the same pre-existing `test_empty_meanings`.
Mutation checks (each restored): z threshold disabled fails 1; SE formula replaced fails 2; min-days guard removed fails 3; drawdown factor changed fails 1; short-call
sign ignored fails 1; route ignoring its parameters fails 1.

**Still open in Phase 5:** execution parity (needs decision-time reference price + scheduler fills in the book), strategy-level look-ahead test, uncertainty object,
input-novelty check, per-symbol loss lockout.

- **2026-10-03** — Phase 5.3: parity report built (read-only); found that the paper series is a code replay, not fills, so it is out-of-sample stability, not execution parity. `vinu-research` 1278 -> 1300. Nothing committed.

### 5.4: the scheduler's order ledger, and a refused order no longer reported as "submitted" — DONE 2026-10-03

**Why:** execution parity (what a backtest assumed vs what an order actually did) needs a durable record of every order the scheduler tried. The scheduler
path writes nothing to the trade-plan book (and must not: the orchestrator reconciles that book against the broker), so after an hour there was only log text.

**What was built:** `vinu-live/vinu_live/execution_log.py` -- `ExecutionLog`, an append-only SQLite table `scheduler_executions` in its own file
`<data_root>/execution_log.db`, written by `LiveScheduler._execute_plan` for **every slice**: placed, refused, errored, and gate-skipped (with the reason).
Each row: cycle id, symbol, side, qty, slice n/total, order type, `reduce_only`, **the reference price the order was sized at**, **the spread at decision
time**, limit price, client order id, outcome, HTTP status, broker order id and broker status, reason. `GET /live/executions?limit=&symbol=` returns the rows
newest-first with counts by outcome and reference-price / spread coverage. Log-only: `record` never raises (a broken ledger never stops an order), and
`execution_log_enabled` (env `VINU_LIVE_EXECUTION_LOG_ENABLED`, **default ON**; off = no file) controls it.

**New bug found and fixed (audit item A10):** `POST /agent/broker/order` answers **HTTP 200 even when OrderGuard refuses the order** (`{"status": "rejected", ...}`),
holds it for confirmation (`pending_confirmation`) or the broker call fails (`{"status": "error"}`). The scheduler called every HTTP < 400 answer
"submitted" without reading the body, so a refused order was reported as placed in the cycle result and logs (the orchestrator does read the body:
`order_result.get("status") == "submitted"`). Now `_order_outcome` reads it: `rejected` / `pending_confirmation` / `error` are reported as such with the
reason (and its code); a missing, unreadable or unrecognised body still reads as `submitted` (old behavior), HTTP >= 400 stays `failed`. Applied
unconditionally -- it changes what is reported, never what is sent. The existing "partial fills" warning now counts refusals too.

**Limits:** it records the *submission* answer, not the fill price (an order is usually still working when the answer returns); getting the fill needs an
order-lookup route on the agent API (there is only positions / account today) and a follow-up enrichment pass. The ledger holds the sizing reference price (last
daily close), not a live quote. Only scheduler orders are recorded (the orchestrator has its own book). Until fills are joined in, the slippage side of
execution parity still cannot be computed -- this step makes sure the inputs are being kept from the first order on.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/execution_log.py` | **created** (`ExecutionLog`: record / recent / summary) |
| `vinu-live/vinu_live/scheduler.py` | modified: ledger init / close, `_current_cycle_id`, `_order_outcome`, `_log_execution`, rows for placed / refused / errored / skipped slices |
| `vinu-live/vinu_live/config.py` | modified: `execution_log_enabled` + env |
| `vinu-live/vinu_live/server/app.py` | modified: `GET /live/executions` |
| `vinu-live/tests/test_scheduler_execution_log.py` | **created**, 21 tests (every body status -> outcome, reason with code, HTTP error / unreadable body / exception, row contents, rejected / errored / skipped / reduce-only rows, missing price stays NULL, disabled = no file, broken ledger never stops an order, ledger swallows its own errors, summary, whole cycle reports a refusal as refused, route none / rows / filters, flag/env) |

**Tests:** `vinu-live` 729 -> **750** (+21), same 3 pre-existing errors. Mutation checks (each restored): ignoring the body fails 6; dropping the reference price fails 1;
mis-labelling skipped rows fails 1; letting the ledger raise fails 1; ignoring the flag fails 1.

- **2026-10-03** — Phase 5.4: scheduler order ledger + fix for refused orders reported as submitted. `vinu-live` 729 -> 750. Nothing committed.

### A2 follow-up: close the symbols the scheduler itself opened — DONE 2026-10-03 (part of the A2 flag)

**Decision (replaces the open question):** with `scheduler_respect_trade_plan_symbols` on, a held position that nothing targets is handled by who owns it:
- orchestrator-owned -> left alone (as before);
- **scheduler-owned -> closed**: the order ledger (`execution_log.db`) shows an accepted BUY for it (`ExecutionLog.bought_symbols`), or it is in `scheduler_adopted_symbols`
  (`VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS`, comma-separated: for positions opened before the ledger existed);
- **anything else -> left alone** (a hand-placed holding, or anything this path cannot identify);
- ownership unknown (active-plan read failed) -> nothing is closed.
The cycle now also fetches prices for those symbols; before, a symbol with no target had no price, the translator skipped it, and nothing was ever closed. Reported as
`ownership.orphans_to_liquidate` in the cycle result.

**Limits:** "ever had a BUY accepted" is not "still holds only what it bought" and accepted is not filled, so a symbol the scheduler bought and you later added to by hand would
be closed in full -- list nothing in `scheduler_adopted_symbols` you want kept, and keep hand-placed holdings in symbols the scheduler never trades. If the portfolio has no
targets at all the cycle still skips (an old rule), so a fully retired portfolio is not closed by this. Flag off = nothing here applies.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/execution_log.py` | modified: `bought_symbols()` |
| `vinu-live/vinu_live/config.py` | modified: `scheduler_adopted_symbols` + env |
| `vinu-live/vinu_live/scheduler.py` | modified: `_apply_symbol_ownership` three-way rule, `orphans_to_liquidate`, orphan prices fetched |
| `vinu-live/tests/test_scheduler_allocation_and_ownership.py` | modified: +10 tests (retired symbol closed; hand-placed never touched; only accepted buys count; adopted symbols; orchestrator-owned never closed; unknown ownership closes nothing; still-targeted is not an orphan; no ledger -> nothing; flag off -> nothing; env) |

**Tests:** `vinu-live` 750 -> **759**, same 3 pre-existing errors. Mutation checks (each restored): not pricing orphans fails 2; treating every untargeted symbol as an orphan fails 4; closing on
unknown ownership fails 1; counting rejected buys fails 1; ignoring the adopted list fails 1.

- **2026-10-03** — A2 follow-up: scheduler closes only the symbols it opened (ledger / adopted list); open Phase 4 questions closed. `vinu-live` 750 -> 759. Nothing committed.

### Loud failure when the broker cannot be reached — DONE 2026-10-03 (notification only, ON by default)

**What was built:** when the broker (Alpaca, reached through the agent API) cannot be read, the scheduler now says so loudly instead of one quiet log line.
A "broker problem" is any of: the positions read fails, a **configured** broker's equity cannot be read (this fires even with the A7 abort flag off), or an order
submission fails at the HTTP / broker level (`failed` / `error`). A refused order (`rejected`) and an unconfigured broker are NOT outages. At the end of every cycle
that reached the broker reads (`_finish_broker_health`):
- an **ERROR log** line naming the reasons and the consecutive-bad-cycle count;
- `broker_unreachable: [reasons]` in the cycle result;
- one **CRITICAL notification** on the first bad cycle, a reminder every `broker_unreachable_renotify_cycles` consecutive bad cycles (default 6), and **one
  "recovered" message** when it works again. It reuses the existing `/notify/reconciliation-drift` front door with `symbol="BROKER"` and actions
  `broker_unreachable` / `broker_recovered`; the agent route gives them their own headers (`[BROKER UNREACHABLE] ... No orders can be sized or placed until it is
  reachable.` / `[Broker recovered]`) and no "manual review" footer.
It never changes what the scheduler does (the cycle still fails / still falls back exactly as before). `broker_unreachable_notify_enabled` (env
`VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED`, default ON) turns the notification off; the log line and the result field stay.

**Limits:** the notification travels through the agent API, so if the **agent API itself** is down the alert cannot be delivered (the ERROR log is then the only trace) --
catching that needs an external heartbeat, not this. The agent's noise gate (dedup window / cooldown / quiet hours) can still suppress a repeat. A cycle that skips before
any broker read (no target weights) neither raises nor clears a streak. On the question "store the last good account state": deliberately not done for sizing -- sizing on a
stale equity is the same class of risk A7 removed; the loud alert plus the A7 abort is the safe answer.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/scheduler.py` | modified: `_broker_problems`, `_finish_broker_health`, `_notify_broker_health`; problems recorded at the positions read, the equity read and order failures |
| `vinu-live/vinu_live/config.py` | modified: `broker_unreachable_notify_enabled`, `broker_unreachable_renotify_cycles` + env |
| `vinu-agent/vinu_agent/server/routes_notify.py` | modified: `broker_unreachable` / `broker_recovered` message formats |
| `vinu-live/tests/test_scheduler_broker_unreachable.py` | **created**, 13 tests (healthy says nothing; positions / equity (flag off) / order failures reported; unconfigured and refused are not outages; edge-triggered, reminder every N, recovery once; disabled; failing notification harmless; no leak between cycles; a skipped cycle leaves the streak) |
| `vinu-live/tests/test_scheduler_equity_abort.py` | modified: its "no orders" assertion now ignores the notification post |
| `vinu-agent/tests/test_routes_notify.py` | modified: +1 test (both message formats) |

**Tests:** `vinu-live` 759 -> **772** (+13), same 3 pre-existing errors; vinu-agent notify file 17 pass. Mutation checks (each restored): not recording the positions problem fails 5;
reminding every cycle fails 1; no recovery message fails 1; ignoring the flag fails 1; counting an unconfigured broker fails 1.

- **2026-10-03** — Loud broker-unreachable reporting (log + result + CRITICAL notice + recovery). `vinu-live` 759 -> 772. Nothing committed.

### 5.5: fill prices and slippage in the order ledger — DONE 2026-10-03 (read-only toward the broker, ON by default)

**What was built:** the order ledger (5.4) now learns how each accepted order actually ended up.
- **Agent API:** `AlpacaBroker.get_order(order_id)` (`GET /v2/orders/{id}`) and `GET /agent/broker/order/{order_id}`: status, quantity, filled quantity and
  `filled_avg_price`. Like `/broker/account`, problems come back in the body (`ok` / `unconfigured` / `error`), never as a 5xx. Read-only.
- **Decision-time quote mid:** each ledger row now also stores the quote mid fetched together with the spread (`fetch_quote_snapshot`; `fetch_spread_bps` is unchanged
  for the other callers).
- **Enrichment pass:** at the start of every scheduler cycle, `_enrich_execution_fills` asks the broker about up to `execution_fill_enrichment_batch` (25) accepted orders
  younger than 7 days whose status is not yet final (a partial fill keeps being watched) and writes `fill_price`, `filled_qty`, `fill_status`, `fill_checked_at`,
  `slippage_bps`, `slippage_ref`. Any failure -- including the agent API being down -- is swallowed and the same rows are asked again next cycle. It never changes an order.
- **Slippage:** positive = the fill was WORSE than the reference (a buy above it, a sell below it), in basis points. Reference = the decision-time quote mid when recorded,
  else the sizing reference price (the last daily close). `slippage_ref` says which (`mid` / `close`). No fill price or no reference -> NULL, never a made-up number.
- `GET /live/executions` summary now also reports `filled`, `with_slippage`, `mean_slippage_bps`, `median_slippage_bps`.
- Schema v2 of `execution_log.db` via `MIGRATIONS` (an existing v1 file is migrated in place).
Flags (ON by default): `execution_fill_enrichment_enabled` (`VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED`), `execution_fill_enrichment_batch` (`VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH`).

**Limits:** a `close`-referenced slippage includes the overnight gap, so it overstates execution cost; only `mid`-referenced figures are execution slippage in the strict sense
(rows where the quote could not be fetched fall back to `close`). Market orders usually fill within seconds, so most fills are picked up on the next cycle (an hour later at the default
cadence) -- the fill price itself is exact, only its recording is delayed. Scheduler orders only. Nothing consumes slippage yet (see below).

**What this unlocks, not done yet:** compare mean / median `slippage_bps` with the cost the backtests assume (the simulator's cost model), flag a symbol whose realised
cost is far above it, and feed that into sizing / spread gates. That is a consumer and a policy choice, so it waits for paper data to exist.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-agent/vinu_agent/broker/alpaca.py` | modified: `get_order` |
| `vinu-agent/vinu_agent/server/routes_broker.py` | modified: `GET /broker/order/{order_id}` |
| `vinu-agent/tests/test_routes_broker.py` | modified: +5 tests (fill price returned, working order has none, unconfigured / error in body, broker without lookup, Alpaca endpoint) |
| `vinu-live/vinu_live/trade_plan/guards.py` | modified: `fetch_quote_snapshot` |
| `vinu-live/vinu_live/execution_log.py` | modified: schema v2 migrations, `unresolved_orders`, `record_fill`, richer `summary` |
| `vinu-live/vinu_live/scheduler.py` | modified: quote mid recorded, `_enrich_execution_fills` run at the start of each cycle |
| `vinu-live/vinu_live/config.py` | modified: two flags + env |
| `vinu-live/tests/test_execution_fill_enrichment.py` | **created**, 31 tests (quote snapshot per-field fail-open; migration; slippage sign both sides, mid vs close, NULL not invented; unresolved selection; summary; the pass: fills written, partial watched, unusable answers retried, one failure isolated, batch bound, disabled, broken ledger, whole flow; flags) |
| `vinu-live/tests/test_scheduler_execution_log.py` | modified: summary assertion covers the new keys |

**Tests:** `vinu-live` 772 -> **803** (+31), same 3 pre-existing errors; vinu-agent broker + notify route files 46 pass; `vinu-infra` 397. Mutation checks (each restored): slippage sign ignored fails 3;
always using the close fails 8; final statuses not excluded fails 2; batch ignored fails 1; a partial fill treated as final fails 2; mid not recorded fails 1.

- **2026-10-03** — Phase 5.5: fill prices + slippage in the order ledger (agent order-lookup route, enrichment pass). `vinu-live` 772 -> 803. Nothing committed.

### 5.6: per-symbol loss lockout (v1 C1 / v2 gap list) — DONE 2026-10-03 (opt-in, default OFF)

**What was built:** the portfolio-wide cooldown (`cooldown_active`: 2 losses in a row locks ALL entries for 24 h) cannot say "stop re-entering the name that keeps losing". New in
`vinu_live/trade_plan/guards.py`: with `VINU_LIVE_SYMBOL_LOCKOUT_LOSSES` = N > 0 (default **0 = off**), a symbol whose last N closed trades were all losses is locked for new
**entries** for `VINU_LIVE_SYMBOL_LOCKOUT_HOURS` (default 72) after the latest of those losses. A win or flat trade on that symbol resets its streak; the lock ends on its own at
`locked_until`; every lock carries a reason ("symbol lockout: last 2 closed trade(s) in this name all lost (-50.00); entries locked until 2026-10-06 14:00Z").
- Pure core `symbol_lockout(rows, losses, hours, now)`; `symbol_lockout_active(book, symbol)` and `active_symbol_lockouts(book)` read the trade-plan book's closed positions. Any error -> not
  locked (a guard bug must never stop an order); rows without a parseable `closed_at` cannot start a lock (fail-open).
- **Orchestrator:** `_maybe_enter` returns `entry_blocked_by_symbol_lockout` (classified `HOLD`) right after the portfolio-wide cooldown check. Exits are never touched.
- **Scheduler path:** the A4 entry guards (`scheduler_entry_guards_enabled`) gain a `symbol_lockout` guard after cooldown; increases only, reductions always pass.
- **Visibility:** `GET /live/lockouts` lists the symbols currently locked with streak, loss total and expiry (`enabled: false` when off).
- The 2-in-a-row / 72 h figures are guessed starting values, not fitted to anything. Like the cooldown it is configured by environment variable, not `LiveConfig`.

**Limits:** it reads only the trade-plan book, and the scheduler path writes no fills there (edge `book.writes->live.scheduler`), so on the scheduler path it reflects plan-path losses only,
exactly like the existing cooldown. With the default 2-loss setting the portfolio-wide cooldown (checked first, 24 h) fires before the lockout on the same two losses; the lockout is what keeps
one name blocked for the longer 72 h once the cooldown has lapsed. Realised P&L per closed position, not per signal.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/trade_plan/guards.py` | modified: `SYMBOL_LOCKOUT_LOSSES/HOURS`, `symbol_lockout`, `symbol_lockout_active`, `active_symbol_lockouts` |
| `vinu-live/vinu_live/trade_plan/orchestrator.py` | modified: entry check + `entry_blocked_by_symbol_lockout: HOLD` in the action map |
| `vinu-live/vinu_live/scheduler.py` | modified: `symbol_lockout` entry guard |
| `vinu-live/vinu_live/server/app.py` | modified: `GET /live/lockouts` |
| `vinu-live/tests/test_symbol_lockout.py` | **created**, 20 tests (disabled values; streak / total / expiry; fewer than N; a win or flat resets; expiry; order independence; unparseable and naive timestamps; real book: locked vs other symbols, a win frees it, default off, broken book, listing; orchestrator refuses / enters elsewhere / off; scheduler blocks increase never reduce / off; route) |

**Tests:** `vinu-live` 803 -> **823** (+20), same 3 pre-existing errors. A completeness test (`test_orchestrator_action_classify`) forced the new action string into the HOLD map. Mutation checks
(each restored): a win not resetting the streak fails 3; a lock that never expires fails 1; off-by-one threshold fails 5; orchestrator not wired fails 1; scheduler not wired fails 1; counting every
symbol's losses fails 3.

- **2026-10-03** — Phase 5.6: per-symbol loss lockout (opt-in). `vinu-live` 803 -> 823. Committed up to 5.5 (39281bd0, 694dbd43); 5.6 not yet.

### Phase 3 extension: every wired edge is now instrumented — DONE 2026-10-03

**What was built:** the runtime recorder (your "expected inputs per step, logged when they do not arrive" idea) now covers **all 34 wired edges** in `pipeline_edges.yaml`
(it was 9 of 35). Each consumption point records `received` / `empty` / `missing` (and `stale` where a cadence is known). The one remaining edge, `book.writes->live.scheduler`,
is a declared known gap, so the manifest has no `not_instrumented` edge left. `GET /research/pipeline-edges?only_problems=true` therefore shows, for the first time, every
connection that is silent, empty where it should not be, or failing -- including the ones that used to fail without a trace.

The 25 edges added, by service (the status each records, and the situation worth noticing):
- **vinu-live scheduler:** `guard.cooldown` (received), `guard.data_freshness` (**missing** when a symbol has no bar timestamp), `guard.turbulence` (**missing** when the closes fetch fails or is empty),
  `order.reduce_only` (received when an exit is accepted, **missing** when one is refused), `precondition_held` (**missing** when the agent did not state it), `reconciliation_drift->agent.notify`
  (**missing** when the notice is not delivered), `live_decision.entry_price<-scheduler` (received / empty), `live_decision.unsized_executes` (received / empty).
- **vinu-live other:** `research.created_trade_plans->approval_worker` (missing on HTTP error or exception; `stale` after 3,000 s), `strategy.stop_rules->poller` (received only when a stop or max-hold is configured,
  else empty), `live_decision.stuck_trigger->agent.notify` (received / missing).
- **vinu-agent:** `portfolio.risk_status` and `portfolio.state` at the order guard (missing on a failed read, which still fails open), `maturity.status`, `reflection.notable_beliefs` and
  `research.unconfirmed_moves` in the live-decision context tool (its `_fetch_json` could not tell a failed read from an empty answer; it can now), `reflection.synthesis`, `signal_evidence->hypothesis_registry`
  (**missing** when vinu-research is not importable in that deployment), `evaluation_status->idea_prompt` (**missing** when `VINU_STRATEGY_EVAL_DATA_ROOT` is unset in that service), `screener.top->planner_worker`.
- **vinu-portfolio:** `drawdown_status->allocation` (**empty** when the drawdown monitor has never written a status: the halve / flat / halt ladder is then silently running on its default),
  `maturity.status->capital` (when gating is on), `portfolio.not_funded_history->api`.
- **vinu-strategy:** `strategy.run_quality->runs_api` (received per run, with the degraded / sanity facts in the detail).
- **vinu-research:** `sweep.base_code_hash->graveyard` (**empty** when the code-hash join links nothing).

**One deployment change:** `docker-compose.yml` gives `portfolio-api` and `quant-core-api` (vinu-strategy + simulator) the same shared mount the other services already use for edge recording
(`./data/strategy-evaluation:/strategy-eval`, `VINU_STRATEGY_EVAL_DATA_ROOT`). Without it their edges would record nowhere. It is additive; rebuild / recreate those two containers for it to take effect.

**Limits:** recording says an input arrived and when, not that it is correct. Event-driven edges (a refused exit, a stuck trigger) have no cadence, so they never go `stale`; they show `never_seen` until the
first event. Edges in a service that was not restarted with the mount record nothing and read as `never_seen`. `signal_evidence` and similar worker edges depend on that worker actually running in the agent container.

| File (inside `vinu-components/`) | Action |
|---|---|
| `vinu-live/vinu_live/scheduler.py`, `live_decision/poller.py`, `trade_plan_approval_worker.py` | modified: `record_edge` at each site |
| `vinu-agent/vinu_agent/broker/order_guard.py`, `tools/get_live_decision_context_tool.py`, `tools/reflection_synthesis_tool.py`, `tools/screener_client.py`, `agent/scheduler_workers.py` | modified |
| `vinu-portfolio/vinu_portfolio/service.py`, `vinu-strategy/vinu_strategy/service.py`, `vinu-research/vinu_research/candidate_graveyard.py` | modified |
| `vinu-infra/pipeline_edges.yaml` | modified: 25 edges `instrumented: true` (+ `stale_after_sec` on the approval worker; two edges list the sibling file that holds the call) |
| `docker-compose.yml` | modified: shared edge mount for portfolio-api and quant-core-api |
| `vinu-live/tests/test_edge_instrumentation_more.py` | **created**, 24 tests |
| `vinu-agent/tests/test_edge_instrumentation_agent.py` | **created**, 20 tests |
| `vinu-portfolio/tests/test_edge_instrumentation_portfolio.py` | **created**, 6 tests |
| `vinu-strategy/tests/test_run_quality_metadata.py`, `vinu-research/tests/test_sweep_code_hash_and_param_diff.py` | modified: +2 and +3 tests |
| `vinu-research/tests/test_routes_introspect_pipeline_edges.py` | modified: no wired edge can be `not_instrumented` any more |

**Tests:** `vinu-live` 823 -> **847** (+24), `vinu-portfolio` 276 -> **282** (+6), `vinu-strategy` 150 -> **152** (+2; the 10 old env errors unchanged), `vinu-research` 1300 -> **1302** (+2 net; same 1
pre-existing failure `test_empty_meanings`), `vinu-agent` 1522 passed with the 20 new ones (**16 failed / 2 errors, the same as before this work**), `vinu-infra` 397 (its static check proves every `instrumented` edge has
its id in a consumer file). Mutation checks (each restored): precondition recording, reduce-only missing, empty-vs-failed in the context tool, the unset evaluation root, the never-written drawdown monitor, a failed risk-budget read, the
run-quality status -- each failed 1-2 tests.

- **2026-10-03** — Phase 3 extension: all 34 wired edges instrumented (was 9); compose gives portfolio and quant-core the shared edge mount. Nothing uncommitted before this; this work is committed with it.
