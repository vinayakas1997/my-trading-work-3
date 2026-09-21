# Implementation plan

Status: **not started**. This is the concrete build plan for everything
diagnosed in `00-explanation.md` — read that first if you haven't; this
file assumes its findings (the K-cap bug, the 10 real evaluation steps,
the mixed persistence state, the 3 post-ACTIVE mechanisms) without
re-explaining them.

---

## 1. The 3-table schema — new `vinu-infra` module

**New file: `vinu-infra/strategy_evaluation.py`** (flat, at the top
level of the `vinu-infra` package — matching `reflection.py`,
`calibration_log.py`, `trade_audit_log.py`'s own layout, **not** a
`vinu-infra/vinu_infra/` subdirectory. That subdirectory was a real,
confirmed packaging bug once already this session — `freeze.py` lived
there and was completely unimportable until moved flat. Don't repeat it.)

Both `vinu-agent` and `vinu-research` already depend on `vinu-infra` —
this is the one place both services can write to without either
depending on the other (the same constraint that made `MaturityAssessor`
get a separate copy in `vinu-research` instead of importing
`vinu-agent`).

### Table 1 — `strategy_evaluation_history` (append-only)

```sql
CREATE TABLE IF NOT EXISTS strategy_evaluation_history (
    log_id          TEXT PRIMARY KEY,
    artifact_id     TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    step_name       TEXT NOT NULL,
    step_order      INTEGER NOT NULL,
    verdict         TEXT NOT NULL,   -- PASS | FAIL | HOLD
    reasoning       TEXT NOT NULL DEFAULT '',
    metrics_json    TEXT NOT NULL DEFAULT '{}',
    computed_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seh_artifact ON strategy_evaluation_history(artifact_id);
CREATE INDEX IF NOT EXISTS idx_seh_ticker ON strategy_evaluation_history(ticker, computed_at);
```

One row per real step attempt. Never updated, never deleted — the full
audit trail. A candidate that gets re-evaluated at the same step twice
(e.g. `decay-scan` checking an ACTIVE strategy every 24h) just gets
another row; that's real history, not a bug.

### Table 2 — `strategy_evaluation_status` (upserted, current state)

```sql
CREATE TABLE IF NOT EXISTS strategy_evaluation_status (
    artifact_id           TEXT PRIMARY KEY,
    ticker                TEXT NOT NULL,
    furthest_step_passed  INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL,   -- in_progress | rejected | active | decayed
    rejected_at_step      TEXT,
    rejected_reason       TEXT,
    last_updated          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ses_ticker ON strategy_evaluation_status(ticker);
```

Fast "where does this candidate stand right now" read, no join or scan
of table 1 needed. Recomputed from table 1 on every write (see `write_step_result()`
below) — table 2 is a derived cache of table 1, never a second source of
truth. If they ever disagree, table 1 is authoritative.

### Table 3 — `strategy_evaluation_step_registry` (static, seeded)

```sql
CREATE TABLE IF NOT EXISTS strategy_evaluation_step_registry (
    step_name               TEXT PRIMARY KEY,
    step_order               INTEGER NOT NULL,
    service_owner            TEXT NOT NULL,
    kind                     TEXT NOT NULL,
    description               TEXT NOT NULL,
    pass_rule                TEXT NOT NULL,
    reject_examples           TEXT NOT NULL DEFAULT '[]',
    current_thresholds_json  TEXT NOT NULL DEFAULT '{}',
    source_file              TEXT NOT NULL,
    updated_at               REAL NOT NULL
);
```

Seeded idempotently on every service startup (same "seed on every start,
never clobber a manual edit" posture as `vinu-screener seed-default` and
`reflection.py`'s `upsert_reference_config`) — see section 3 for the
real seed values for all 10 steps.

### The module's real functions

```python
def write_step_result(store, *, artifact_id, ticker, step_name, verdict,
                       reasoning, metrics=None) -> None:
    """Writes one history row, then recomputes and upserts the status
    row from the full history for this artifact_id. The one function
    every real step (all 10) calls -- mirrors reflection.py's
    write_finding() as the single funnel point."""

def get_status(store, artifact_id) -> dict | None: ...
def list_status_for_ticker(store, ticker) -> list[dict]: ...
def get_history(store, artifact_id) -> list[dict]: ...
def get_step_definition(store, step_name) -> dict | None: ...
def seed_step_registry(store) -> None:
    """Idempotent upsert of all 10 real step definitions -- see section 3."""
```

---

## 2. Wiring — where each of the 10 real writes actually go

Each of these is a **small, additive edit** to code that already exists
and already produces a verdict + reasoning — this plan does not change
any step's actual pass/fail logic, only adds one `write_step_result()`
call at the point the verdict is already known.

| step_name | Real call site(s) | step_order | Status |
|---|---|---|---|
| `risk_critic` | **Real site differs from the plan's guess**: not inside `loop.py` (no artifact exists there yet) — `vinu-research/vinu_research/service.py`'s `approve_run()`, reading the final iteration's verdict back via the already-existing `iteration_checkpoints.critic_verdict` column | 1 | **Wired** — only the verdict string survives (not the full reasoning text, which was never persisted anywhere), documented honestly in the written `reasoning` field |
| `promotion_bar` | **3 real call sites, not 1** (found while implementing): `vinu-research/vinu_research/cli.py`'s `promote-scan`, `vinu-research/vinu_research/service.py`'s `approve_run()`, **and** `vinu-agent/vinu_agent/agent/capital_allocator_hook.py`'s own independent re-check before funding (a deliberate second enforcement point, not a duplicate — see that file's own G1 docstring) | 2 | **Wired**, all 3 sites |
| `correlation_gate` | **2 real call sites**: `cli.py`'s `promote-scan` (reuses the verdict `build_correlation_verdict()` already computes) and `service.py`'s `approve_run()` (the independent fresh-research-run path) | 3 | **Wired**, both sites |
| `risk_gatekeeper` | `vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py` — both branches (REJECTED and APPROVED/PEND) | 4 | **Wired** |
| `capital_allocator` | `vinu-agent/vinu_agent/agent/capital_allocator_hook.py` — kill-switch-engaged (`HOLD`, not just PASS/FAIL) and real-funding-succeeds branches | 5 | **Wired** |
| `shadow_evaluator` | `vinu-live/vinu_live/shadow_evaluator.py`'s `_evaluate_one()` — the `auto_paused` fast-path (FAIL) and the `promoted`/`below_threshold` split (PASS/FAIL). `insufficient_data` writes nothing (nothing decided yet) | 6 | **Wired** |
| `decay_scan` | `vinu-research/vinu_research/cli.py`'s `_run_decay_scan()`, right after each artifact's real `DecaySnapshot` is computed | 7 | **Wired** |
| `trade_score_gate` | **Real site differs from the plan's guess**: `check_trade_score_gate()` itself is a pure function with no artifact context — wired instead at `trade_plan_authoring.approve_trade_plan()`'s frozen-tier re-check, the one real place both gates share force/approver logic (per that function's own docstring) | 8 | **Wired** |
| `approve_trade_plan` | `vinu_research.trade_plan_authoring.approve_trade_plan()` — both real branches (bootstrap-from-ACTIVE-strategy, or `CalibrationGate`). `force=True` records the real underlying verdict, never silently flipped to PASS — `forced`/`approver` go into `metrics_json` instead | 9 | **Wired** |
| `order_guard` | `vinu-agent/vinu_agent/tools/trade_tool.py`, right after `result = guard.check(...)` — the structurally-unbypassable choke point (`00-explanation.md` section 5). Real artifact linkage via `_resolve_active_artifact_id()`, reusing `OrderGuard._check_active_artifact()`'s own in-process lookup; synthetic `f"order:{symbol}"` id only as genuine last resort (no ACTIVE artifact exists) | 10 | **Wired**, with real artifact-id resolution (not just the synthetic fallback) |

See `02-implementation.md` for the full, dated build log — this table is kept in sync with it, not a duplicate source of truth.

**New dependency**: `vinu-research` needs `vinu-infra` (almost certainly
already has it, since `vinu-infra` is the base shared package — confirm
during implementation, don't assume). No new docker-compose mount
needed — this is a new SQLite table inside each service's own existing
data root, written in-process, not read cross-service via HTTP or mount.

**Open question, real, not yet resolved**: `strategy_evaluation.db`
needs to live somewhere both `vinu-agent` and `vinu-research` can write
to. Since services don't share a data volume today (each has its own
`./data/<service>` mount), this either needs (a) a new shared
`./data/strategy-evaluation` volume mounted read-write into both
`agent-api` and `research-api` in `docker-compose.yml`, or (b) two
separate per-service DB files with a later read-side merge. **(a) is
simpler and more honest** (one real table, not two that need
reconciling) — recommended, but confirm before building since it's a
real docker-compose change, not just application code.

---

## 3. Real seed values for the step registry (table 3)

Concrete, not placeholder — these are the real files/checks already
verified in `00-explanation.md`:

```python
STEP_DEFINITIONS = [
    dict(step_name="risk_critic", step_order=1, service_owner="vinu-research",
         kind="LLM specialist",
         description="Judges whether the strategy is statistically sound: backtest metrics (Sharpe, drawdown, win rate, trade count) plus statistical validation (Monte Carlo, bootstrap, walk-forward).",
         pass_rule="Trade count >= ~20 AND statistical validation not failed for real reasons (e.g. bootstrap CI lower bound at/below zero, walk-forward consistency well under 0.5) -> PASS; otherwise STOP.",
         source_file="vinu-agent/teams/research/agents/risk_critic/prompt.md"),
    dict(step_name="promotion_bar", step_order=2, service_owner="vinu-research",
         kind="deterministic",
         description="BENCHING -> ACTIVE/MONITORING gate on hard statistical thresholds.",
         pass_rule="deflated_sharpe >= config threshold AND holdout_passed (if required) AND pbo <= config threshold.",
         source_file="vinu-research/vinu_research/promotion.py:30"),
    dict(step_name="correlation_gate", step_order=3, service_owner="vinu-research",
         kind="deterministic",
         description="Is the candidate too correlated with strategies already ACTIVE?",
         pass_rule="avg/max correlation against each ACTIVE strategy below config threshold -> eligible=True.",
         source_file="vinu-research/vinu_research/gates/correlation_gate.py"),
    dict(step_name="risk_gatekeeper", step_order=4, service_owner="vinu-agent",
         kind="LLM team",
         description="NOT a quality check -- only whether the strategy fits the CURRENT real portfolio's risk limits (exposure/concentration) right now.",
         pass_rule="exposure_reviewer's real-portfolio check returns APPROVED with an approved_size.",
         source_file="vinu-agent/teams/risk_gatekeeper/manager_prompt.md"),
    dict(step_name="capital_allocator", step_order=5, service_owner="vinu-agent",
         kind="deterministic worker",
         description="Funds PEND artifacts on its own batched cadence, decides real dollar sizing.",
         pass_rule="Batch cadence run reaches this artifact and real capital is available to allocate.",
         source_file="vinu-agent/vinu_agent/cli.py (capital-allocator-worker)"),
    dict(step_name="shadow_evaluator", step_order=6, service_owner="vinu-live",
         kind="deterministic",
         description="Compares real paper-trading P&L against what the backtest predicted, before real capital is committed.",
         pass_rule="Real paper P&L within tolerance of backtest-predicted performance.",
         source_file="vinu-live/vinu_live/shadow_evaluator.py"),
    dict(step_name="decay_scan", step_order=7, service_owner="vinu-research",
         kind="deterministic, scheduled every 24h",
         description="Ongoing health check for an already-ACTIVE strategy -- rolling Sharpe/IC/IR against its own historical baseline.",
         pass_rule="evaluate_health() score >= 0 (HEALTHY or WARNING); DECAYED/CRITICAL triggers the transition + auto re-research.",
         source_file="vinu-research/vinu_research/decay.py"),
    dict(step_name="trade_score_gate", step_order=8, service_owner="vinu-research",
         kind="deterministic",
         description="Re-checks the Trade Score tier frozen onto a trade plan at authoring time, at approval time (approve_trade_plan()) -- a composite of confluence, EV, and regime-fit sub-scores against config.min_tradeable_tier (default 'watch').",
         pass_rule="tier_meets_minimum(tier, config.min_tradeable_tier) -- tier order is no_trade < watch < moderate < strong.",
         source_file="vinu-research/vinu_research/gates/trade_score_gate.py"),
    dict(step_name="approve_trade_plan", step_order=9, service_owner="vinu-research",
         kind="deterministic, fail-closed",
         description="Approves/rejects one specific trade plan based on real calibration history.",
         pass_rule="Enough real calibration history exists to trust this specific plan; a fresh plan with no history bootstraps off the symbol's own ACTIVE artifact (which already cleared promotion_bar) or is rejected.",
         source_file="vinu_research.trade_plan_authoring.approve_trade_plan()"),
    dict(step_name="order_guard", step_order=10, service_owner="vinu-agent",
         kind="deterministic, structurally unbypassable (verified)",
         description="The final, real-time gate immediately before an order is placed -- symbol limits, kill switch, daily order caps.",
         pass_rule="guard.check(symbol, side, qty, ...) returns truthy with no needs_reauth.",
         source_file="vinu-agent/vinu_agent/broker/order_guard.py"),
]
```

`reject_examples` and `current_thresholds_json` are deliberately left
empty in this seed list — those should be filled from real observed
rejections/config once the system has been running with this wired in,
not invented now.

---

## 4. Fix 1 — the K-cap bug — **DONE, Option B, the real fix**

**Superseded, 2026-09-21**: this section originally shipped as Option A
(a 7-day rolling time window), reasoned as a stopgap because Option B
appeared to need a `run_id→artifact_id` join that didn't exist. That
premise was wrong — **user correction**: the cap never needed to count
proposal *events* at all. It needs to count **currently-open artifacts
for the ticker**, and the whole system is already organized around
`artifact_id` (machine-proposed and human-submitted strategies both
produce the same `Artifact` row) — the exact lookup already existed and
was already used elsewhere in the same function for recipe rotation:
`strategy_store.list_artifacts_for_symbol(ticker,
statuses=NON_TERMINAL_STATUSES)`. No join was ever required.

**Built Option B**: both real call sites
(`thesis_intake_gate.py`/`planner_triage_hook.py`) now count
`len(list_artifacts_for_symbol(ticker, NON_TERMINAL_STATUSES))` directly
instead of a ledger-event count. `K_CAP_WINDOW_DAYS`/
`_k_cap_window_since()` are kept in `thesis_intake_gate.py` as a real
fallback for the one call path where no `strategy_store` is available,
not deleted outright.

**No time-based control needed on top of this**: decay (`decay_scan`,
step 7) already auto-transitions a strategy to `decayed`/`disabled`
when it stops working, which frees its K-cap slot the moment that
happens. A fixed cap of currently-open artifacts, with decay doing the
real-time freeing, is the complete mechanism.

**Real gap this surfaced and closed** (explicit user "go ahead" before
building): artifact-count-based capping only works if rejected
candidates actually become terminal. Before this round, a
`promotion_bar` FAIL left the artifact stuck in `BENCHING` forever,
permanently occupying a slot. Fixed by transitioning to
`ArtifactStatus.DISABLED` at all real `promotion_bar` call sites —
`cli.py`'s `promote-scan`, `capital_allocator_hook.py`'s re-check, and a
**fourth real call site found while closing this gap**,
`routes_read.py`'s `POST /artifacts/{id}/promote` (previously never
wired for `strategy_evaluation` at all, in any prior round). This split
is deliberate, not uniform: `promotion_bar` FAIL → `DISABLED`
(permanent — its metrics are fixed, re-checking can't change the
verdict); `risk_gatekeeper`/`correlation_gate` REJECTED stay
re-checkable (portfolio state and inter-strategy correlation can
legitimately change). See `02-implementation.md` for the full account
and test coverage.

**File**: `vinu-agent/vinu_agent/agent/planner_triage_hook.py`

Now:
```python
existing = self._strategy_store.list_artifacts_for_symbol(ticker, statuses=NON_TERMINAL_STATUSES)
if len(existing) >= self._k_cap:
    return PlannerTriageResult(ticker, False, f"ticker at distinct-candidate cap ({len(existing)}/{self._k_cap}) currently non-terminal")
```

---

## 5. Fix 2 — the enhancer loop itself — **DONE**

**Real trigger point turned out simpler than guessed**: not a new hook on
the K-cap check itself — `vinu-agent/vinu_agent/agent/scheduler_workers.py`'s
`make_planner_on_yes()`'s `_on_yes()` already fires exactly once per real
candidate proposal (the same moment `PlannerTriage.check()` says
`should_propose=True`), and it **already had the exact right shape**: it
was already building `prior_rejections` (from `HypothesisRegistry`,
human-submitted theses only) into the `idea_generator` hand-off's task
string. The enhancer just extends this same, already-proven mechanism
with `strategy_evaluation` data instead of inventing a new path.

**New**: `_strategy_evaluation_context_for_ticker(ticker)` in
`scheduler_workers.py`. Queries `list_status_for_ticker(ticker)` and
appends, when real data exists:
- Every candidate still `in_progress`/`active` for this ticker (so the
  new idea doesn't duplicate one already being evaluated).
- The single most recent `rejected` row's `rejected_at_step` +
  `rejected_reason` (the real machine-evaluation chain's own reasons —
  `risk_critic`, `promotion_bar`, etc. — distinct from
  `HypothesisRegistry`'s human-thesis rejections, which stay untouched).

**The open design questions from the original draft, resolved**:
- *Prompt shape*: reuses the exact `"\nPrior rejected hypotheses..."`
  pattern already proven in production, not a new format.
- *How much history*: only the single most recent rejection, not the
  full history — matches "learn from the last mistake," not "relitigate
  every past attempt."
- *Unbounded growth*: naturally bounded by `K_CAP_DEFAULT` itself (at
  most 3 in-flight siblings can ever exist for one ticker at a time) —
  no separate cap needed.

Ships inert (no context added) when `VINU_STRATEGY_EVAL_DATA_ROOT` is
unset or there's no real data yet — same posture as `prior_rejections`
being empty today. 3 new tests in `test_scheduler_workers.py`
(ships-inert, real siblings+rejection appear in the task text, no
history adds nothing). Full `vinu-agent` suite green.

---

## 6. Build order — all done, see `02-implementation.md` for the real account

1. ✅ `vinu-infra/strategy_evaluation.py` — the 3 tables + the 5 real
   functions (section 1).
2. ✅ Shared-data-root — real docker-compose.yml volume + env var,
   mounted into `agent-api`/`research-api`/`live-api`.
3. ✅ All 10 real write call sites wired — several at more real call
   sites than originally guessed (`promotion_bar`: 3, `correlation_gate`:
   2) or at a different site entirely (`risk_critic`, `trade_score_gate`).
4. ✅ K-cap bug fixed — Option B (real artifact count via
   `list_artifacts_for_symbol(NON_TERMINAL_STATUSES)`), superseding the
   earlier Option A (rolling window) shipped first in this same round;
   see `02-implementation.md` for the correction and the DISABLED-on-
   rejection fix it required.
5. ✅ Enhancer loop built — reused an existing, already-proven prompt
   mechanism (`prior_rejections`) rather than inventing a new one.
6. ✅ The read view — `vinu-agent strategy-eval <TICKER>` (not in the
   original numbered list, added once the data existed to build a real
   view against).

## 7. Verify

- Each new/touched package's test suite green after its own step, not
  just at the end.
- Manual/documented: run the real end-to-end test again (main stack +
  the K-cap-affected ticker from this session, AAPL), confirm
  `strategy_evaluation_status` for AAPL's real candidates shows accurate
  `furthest_step_passed`/`rejected_at_step`/`rejected_reason`, and that
  `get_step_definition(store, "promotion_bar")` returns the real,
  current threshold values, not stale ones.
