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

| step_name | Real call site to add the write | step_order |
|---|---|---|
| `risk_critic` | `vinu-research/vinu_research/loop.py:~450`, right after `critic_feedback = await self._risk_critic(...)` | 1 |
| `promotion_bar` | `vinu-research/vinu_research/promotion.py:76`, right after `return PromotionVerdict(eligible=not reasons, reasons=reasons)` — **also fixes the real gap in `00-explanation.md` section 3** (currently only printed to stdout in `cli.py`) | 2 |
| `correlation_gate` | `vinu-research/vinu_research/gates/correlation_gate.py`, right after `CorrelationVerdict` is built | 3 |
| `risk_gatekeeper` | `vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py:63-74` — already writes to `TickerLedger`; add the same info to this new table alongside it, don't remove the existing write (other things may already depend on it) | 4 |
| `capital_allocator` | `vinu-agent/vinu_agent/cli.py`'s `capital-allocator-worker`, at the point funding is decided | 5 |
| `shadow_evaluator` | `vinu-live/vinu_live/shadow_evaluator.py`, at the point it decides "promote" vs "not yet" | 6 |
| `decay_scan` | `vinu-research/vinu_research/cli.py:544`, right after `art.status = new_status` | 7 |
| `trade_score_gate` | `vinu-research/vinu_research/gates/trade_score_gate.py`, at its real verdict point | 8 |
| `approve_trade_plan` | `vinu_research.trade_plan_authoring.approve_trade_plan()`, at its real verdict point | 9 |
| `order_guard` | `vinu-agent/vinu_agent/tools/trade_tool.py:297`, right after `result = guard.check(...)` | 10 |

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
         description="Per-trade-plan-authoring check (not artifact-level) -- EV/regime fit at the moment a trade plan is generated.",
         pass_rule="See vinu-research/vinu_research/gates/trade_score_gate.py's real thresholds -- not yet read in this pass, fill in during implementation.",
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

## 4. Fix 1 — the K-cap bug (self-contained, do this first)

**File**: `vinu-agent/vinu_agent/agent/planner_triage_hook.py:103`

Current:
```python
count = self._ticker_ledger.count_events(ticker, event_type=CANDIDATE_PROPOSED_EVENT_TYPE)
```

Real fix — two real options, pick one deliberately, don't guess:

**Option A — rolling time window** (matches the log message's own
"this cycle" wording most literally):
```python
count = self._ticker_ledger.count_events(
    ticker, event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
    since=<some real window, e.g. now - 24h>,
)
```
Needs a real decision on the window size — not specified anywhere yet,
would need to be a new config value, not a hardcoded guess.

**Option B — discount terminal (rejected/expired) candidates from the
count**, keeping it otherwise all-time. Requires knowing, per
`candidate_proposed` event, whether that candidate is still open or was
already terminally rejected — which is exactly what table 2
(`strategy_evaluation_status`) will be able to answer once section 1-3
are built. **This option becomes trivial once the new tables exist** —
count only artifacts with `status IN ('in_progress', 'active')` for this
ticker, not `count_events()`'s raw ledger count at all.

**Recommendation**: build the 3 tables first (sections 1-3), then fix
the cap using Option B — it's the more correct fix (a candidate that's
still genuinely in flight should count against the cap; one that's
already resolved shouldn't, regardless of how much time has passed) and
it falls out naturally once the status table exists, rather than needing
a second, separate time-window config value.

---

## 5. Fix 2 — the enhancer loop itself

Once sections 1-4 exist, the actual "learn from rejection" piece:

1. **Trigger point**: `planner_triage_hook.py`'s cap check (now backed
   by table 2, per section 4 Option B) sees a freed slot for a ticker.
2. **Before generating a new candidate**, query:
   - `list_status_for_ticker(store, ticker)` — the other 1-2 candidates
     still `in_progress`/`active` for this ticker, so the new idea's
     prompt can be told "don't propose something like these."
   - The most recent `rejected` row for this ticker from table 2 —
     `rejected_at_step` + `rejected_reason`, so the new idea's prompt is
     told specifically what failed and why.
3. **Feed both into the real candidate-generation prompt** — the exact
   prompt-shape change needed is not yet designed; this is genuinely the
   open design question flagged in `00-explanation.md` section 7 (how
   much history to include, how to keep the context from growing
   unbounded as rejections accumulate over a ticker's lifetime — a real
   question, not yet answered here).
4. **Reuse `decay_scan`'s real precedent** (`_trigger_re_research()` in
   `vinu-research/vinu_research/cli.py`) for the actual "kick off a new
   attempt" plumbing shape — it already does steps 1 and (partially) 2
   for the decay case; this is the same shape applied to a K-cap
   rejection instead of a decay event.

---

## 6. Build order

1. `vinu-infra/strategy_evaluation.py` — the 3 tables + the 5 real
   functions (section 1). Tests: schema creation, `write_step_result()`
   recomputes `status` correctly (furthest step, rejected reason),
   `seed_step_registry()` idempotency.
2. Resolve the shared-data-root open question (section 2) —
   docker-compose.yml change, needed before any real cross-service data
   shows up (both services can develop/test against it locally without
   this being resolved, using a shared `tmp_path` in tests).
3. Wire all 10 real write call sites (section 2's table), one at a time,
   each with its own test confirming the write actually happens with
   real verdict/reasoning content, not a placeholder. Run each touched
   service's full test suite after its own step.
4. Fix the K-cap bug (section 4), using Option B once table 2 exists.
5. Build the enhancer loop (section 5) — the piece with real open design
   questions; expect this to need its own follow-up design pass once
   1-4 are running and real data exists to design the prompt against
   (same "don't design in a vacuum" discipline used throughout this
   whole project).

## 7. Verify

- Each new/touched package's test suite green after its own step, not
  just at the end.
- Manual/documented: run the real end-to-end test again (main stack +
  the K-cap-affected ticker from this session, AAPL), confirm
  `strategy_evaluation_status` for AAPL's real candidates shows accurate
  `furthest_step_passed`/`rejected_at_step`/`rejected_reason`, and that
  `get_step_definition(store, "promotion_bar")` returns the real,
  current threshold values, not stale ones.
