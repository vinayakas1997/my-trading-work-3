"""Strategy-enhancer tables (missing-pieces-of-system/startegy-enhancer/
01-plan.md section 1) — the real, cross-service audit trail for every
step a candidate strategy passes through, from `risk_critic` up to
`order_guard`, plus the ongoing post-ACTIVE checks (`shadow_evaluator`,
`decay_scan`).

Lives in vinu-infra, not vinu-agent or vinu-research, because both of
those services need to write to it and vinu-research does not (and must
not) depend on vinu-agent -- see 01-plan.md's own note on this, the same
constraint that already made `MaturityAssessor` get a separate copy in
vinu-research instead of importing vinu-agent's.

Three tables:
- `strategy_evaluation_history` — append-only, one row per real step
  attempt. The audit trail.
- `strategy_evaluation_status` — upserted, one row per artifact_id, the
  current-state view. A derived cache of history, recomputed on every
  write, never a second source of truth.
- `strategy_evaluation_step_registry` — static, seeded once per process
  start (idempotent), the "rulebook": what each step_name actually
  checks and its current real thresholds, so a rejection can always be
  looked up without reading code.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_HOLD = "HOLD"

STATUS_IN_PROGRESS = "in_progress"
STATUS_REJECTED = "rejected"
STATUS_ACTIVE = "active"
STATUS_DECAYED = "decayed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_evaluation_history (
    log_id          TEXT PRIMARY KEY,
    artifact_id     TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    step_name       TEXT NOT NULL,
    step_order      INTEGER NOT NULL,
    verdict         TEXT NOT NULL,
    reasoning       TEXT NOT NULL DEFAULT '',
    metrics_json    TEXT NOT NULL DEFAULT '{}',
    computed_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seh_artifact ON strategy_evaluation_history(artifact_id);
CREATE INDEX IF NOT EXISTS idx_seh_ticker ON strategy_evaluation_history(ticker, computed_at);

CREATE TABLE IF NOT EXISTS strategy_evaluation_status (
    artifact_id           TEXT PRIMARY KEY,
    ticker                TEXT NOT NULL,
    furthest_step_passed  INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL,
    rejected_at_step      TEXT,
    rejected_reason       TEXT,
    last_updated          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ses_ticker ON strategy_evaluation_status(ticker);

CREATE TABLE IF NOT EXISTS strategy_evaluation_step_registry (
    step_name                TEXT PRIMARY KEY,
    step_order                INTEGER NOT NULL,
    service_owner             TEXT NOT NULL,
    kind                      TEXT NOT NULL,
    description                TEXT NOT NULL,
    pass_rule                 TEXT NOT NULL,
    reject_examples            TEXT NOT NULL DEFAULT '[]',
    current_thresholds_json   TEXT NOT NULL DEFAULT '{}',
    source_file                TEXT NOT NULL,
    updated_at                 REAL NOT NULL
);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now_ts() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class StrategyEvaluationStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    # -- history / status --------------------------------------------------

    def write_step_result(
        self,
        *,
        artifact_id: str,
        ticker: str,
        step_name: str,
        step_order: int,
        verdict: str,
        reasoning: str = "",
        metrics: Optional[dict[str, Any]] = None,
    ) -> str:
        """The one funnel every real step (all 10, see 01-plan.md section 2)
        calls -- mirrors reflection.py's write_finding(). Writes one history
        row, then recomputes and upserts the status row from the full
        history for this artifact_id (status is always a derived cache of
        history, never a second source of truth -- if they ever disagree,
        history is authoritative)."""
        log_id = _new_id()
        now = _now_ts()
        self.upsert(
            "strategy_evaluation_history",
            {
                "log_id": log_id,
                "artifact_id": artifact_id,
                "ticker": ticker.upper(),
                "step_name": step_name,
                "step_order": step_order,
                "verdict": verdict,
                "reasoning": reasoning,
                "metrics_json": json.dumps(metrics or {}),
                "computed_at": now,
            },
            conflict_columns=["log_id"],
        )
        self._recompute_status(artifact_id, ticker)
        return log_id

    def _recompute_status(self, artifact_id: str, ticker: str) -> None:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT step_name, step_order, verdict, reasoning, computed_at "
            "FROM strategy_evaluation_history WHERE artifact_id = ? "
            "ORDER BY computed_at ASC",
            (artifact_id,),
        ).fetchall()
        if not rows:
            return

        furthest_step_passed = 0
        status = STATUS_IN_PROGRESS
        rejected_at_step: Optional[str] = None
        rejected_reason: Optional[str] = None

        for row in rows:
            if row["verdict"] == VERDICT_PASS:
                furthest_step_passed = max(furthest_step_passed, row["step_order"])
            elif row["verdict"] == VERDICT_FAIL:
                status = STATUS_REJECTED
                rejected_at_step = row["step_name"]
                rejected_reason = row["reasoning"]

        # A later PASS (e.g. a re-evaluation after decay -> re-research)
        # overrides an earlier rejection -- only the LAST fail with no
        # later pass at a step_order beyond it counts as the current
        # terminal state. Re-scan from the end for the real current state
        # rather than trusting first-seen order.
        for row in reversed(rows):
            if row["step_name"] == "decay_scan" and row["verdict"] == VERDICT_FAIL:
                status = STATUS_DECAYED
                rejected_at_step = row["step_name"]
                rejected_reason = row["reasoning"]
                break
            if row["verdict"] == VERDICT_PASS and row["step_name"] in (
                "capital_allocator", "shadow_evaluator",
            ):
                status = STATUS_ACTIVE
                rejected_at_step = None
                rejected_reason = None
                break
            if row["verdict"] == VERDICT_FAIL:
                status = STATUS_REJECTED
                rejected_at_step = row["step_name"]
                rejected_reason = row["reasoning"]
                break
        else:
            status = STATUS_IN_PROGRESS
            rejected_at_step = None
            rejected_reason = None

        self.upsert(
            "strategy_evaluation_status",
            {
                "artifact_id": artifact_id,
                "ticker": ticker.upper(),
                "furthest_step_passed": furthest_step_passed,
                "status": status,
                "rejected_at_step": rejected_at_step,
                "rejected_reason": rejected_reason,
                "last_updated": _now_ts(),
            },
            conflict_columns=["artifact_id"],
        )

    def get_status(self, artifact_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM strategy_evaluation_status WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_status_for_ticker(self, ticker: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM strategy_evaluation_status WHERE ticker = ? "
            "ORDER BY last_updated DESC",
            (ticker.upper(),),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_history(self, artifact_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM strategy_evaluation_history WHERE artifact_id = ? "
            "ORDER BY computed_at ASC",
            (artifact_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- step registry -------------------------------------------------------

    def upsert_step_definition(
        self,
        *,
        step_name: str,
        step_order: int,
        service_owner: str,
        kind: str,
        description: str,
        pass_rule: str,
        reject_examples: Optional[list[str]] = None,
        current_thresholds: Optional[dict[str, Any]] = None,
        source_file: str,
    ) -> None:
        """Idempotent upsert -- same "seed on every start, never clobber a
        manual edit" posture as reflection.py's upsert_reference_config /
        vinu-screener seed-default."""
        self.upsert(
            "strategy_evaluation_step_registry",
            {
                "step_name": step_name,
                "step_order": step_order,
                "service_owner": service_owner,
                "kind": kind,
                "description": description,
                "pass_rule": pass_rule,
                "reject_examples": json.dumps(reject_examples or []),
                "current_thresholds_json": json.dumps(current_thresholds or {}),
                "source_file": source_file,
                "updated_at": _now_ts(),
            },
            conflict_columns=["step_name"],
        )

    def get_step_definition(self, step_name: str) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM strategy_evaluation_step_registry WHERE step_name = ?",
            (step_name,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_step_definitions(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM strategy_evaluation_step_registry ORDER BY step_order ASC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Real seed data — missing-pieces-of-system/startegy-enhancer/01-plan.md
# section 3. Kept here, not duplicated at each call site, so both
# vinu-agent and vinu-research seed the exact same definitions.
# ---------------------------------------------------------------------------

STEP_DEFINITIONS: list[dict[str, Any]] = [
    dict(
        step_name="risk_critic", step_order=1, service_owner="vinu-research",
        kind="LLM specialist",
        description=(
            "Judges whether the strategy is statistically sound: backtest "
            "metrics (Sharpe, drawdown, win rate, trade count) plus "
            "statistical validation (Monte Carlo, bootstrap, walk-forward)."
        ),
        pass_rule=(
            "Trade count >= ~20 AND statistical validation not failed for "
            "real reasons (e.g. bootstrap CI lower bound at/below zero, "
            "walk-forward consistency well under 0.5) -> PASS; otherwise STOP."
        ),
        source_file="vinu-agent/teams/research/agents/risk_critic/prompt.md",
    ),
    dict(
        step_name="promotion_bar", step_order=2, service_owner="vinu-research",
        kind="deterministic",
        description="BENCHING -> ACTIVE/MONITORING gate on hard statistical thresholds.",
        pass_rule=(
            "deflated_sharpe >= config threshold AND holdout_passed (if "
            "required) AND pbo <= config threshold."
        ),
        source_file="vinu-research/vinu_research/promotion.py:30",
    ),
    dict(
        step_name="correlation_gate", step_order=3, service_owner="vinu-research",
        kind="deterministic",
        description="Is the candidate too correlated with strategies already ACTIVE?",
        pass_rule=(
            "avg/max correlation against each ACTIVE strategy below config "
            "threshold -> eligible=True."
        ),
        source_file="vinu-research/vinu_research/gates/correlation_gate.py",
    ),
    dict(
        step_name="risk_gatekeeper", step_order=4, service_owner="vinu-agent",
        kind="LLM team",
        description=(
            "NOT a quality check -- only whether the strategy fits the "
            "CURRENT real portfolio's risk limits (exposure/concentration) "
            "right now."
        ),
        pass_rule="exposure_reviewer's real-portfolio check returns APPROVED with an approved_size.",
        source_file="vinu-agent/teams/risk_gatekeeper/manager_prompt.md",
    ),
    dict(
        step_name="capital_allocator", step_order=5, service_owner="vinu-agent",
        kind="deterministic worker",
        description="Funds PEND artifacts on its own batched cadence, decides real dollar sizing.",
        pass_rule="Batch cadence run reaches this artifact and real capital is available to allocate.",
        source_file="vinu-agent/vinu_agent/cli.py (capital-allocator-worker)",
    ),
    dict(
        step_name="shadow_evaluator", step_order=6, service_owner="vinu-live",
        kind="deterministic",
        description=(
            "Compares real paper-trading P&L against what the backtest "
            "predicted, before real capital is committed."
        ),
        pass_rule="Real paper P&L within tolerance of backtest-predicted performance.",
        source_file="vinu-live/vinu_live/shadow_evaluator.py",
    ),
    dict(
        step_name="decay_scan", step_order=7, service_owner="vinu-research",
        kind="deterministic, scheduled every 24h",
        description=(
            "Ongoing health check for an already-ACTIVE strategy -- rolling "
            "Sharpe/IC/IR against its own historical baseline."
        ),
        pass_rule=(
            "evaluate_health() score >= 0 (HEALTHY or WARNING); DECAYED/"
            "CRITICAL triggers the transition + auto re-research."
        ),
        source_file="vinu-research/vinu_research/decay.py",
    ),
    dict(
        step_name="trade_score_gate", step_order=8, service_owner="vinu-research",
        kind="deterministic",
        description=(
            "Re-checks the Trade Score tier frozen onto a trade plan at "
            "authoring time, at approval time (approve_trade_plan()) -- a "
            "composite of confluence, EV, and regime-fit sub-scores against "
            "config.min_tradeable_tier (default 'watch')."
        ),
        pass_rule=(
            "tier_meets_minimum(tier, config.min_tradeable_tier) -- tier "
            "order is no_trade < watch < moderate < strong."
        ),
        source_file="vinu-research/vinu_research/gates/trade_score_gate.py",
    ),
    dict(
        step_name="approve_trade_plan", step_order=9, service_owner="vinu-research",
        kind="deterministic, fail-closed",
        description="Approves/rejects one specific trade plan based on real calibration history.",
        pass_rule=(
            "Enough real calibration history exists to trust this specific "
            "plan; a fresh plan with no history bootstraps off the symbol's "
            "own ACTIVE artifact (which already cleared promotion_bar) or "
            "is rejected."
        ),
        source_file="vinu_research.trade_plan_authoring.approve_trade_plan()",
    ),
    dict(
        step_name="order_guard", step_order=10, service_owner="vinu-agent",
        kind="deterministic, structurally unbypassable (verified 2026-09-21)",
        description=(
            "The final, real-time gate immediately before an order is "
            "placed -- symbol limits, kill switch, daily order caps."
        ),
        pass_rule="guard.check(symbol, side, qty, ...) returns truthy with no needs_reauth.",
        source_file="vinu-agent/vinu_agent/broker/order_guard.py",
    ),
]


def seed_step_registry(store: StrategyEvaluationStore) -> None:
    """Idempotent upsert of all 10 real step definitions. Called once per
    process start by every service that writes to this store (same
    posture as every other seed_reference_config call across this
    codebase)."""
    for defn in STEP_DEFINITIONS:
        store.upsert_step_definition(
            step_name=defn["step_name"],
            step_order=defn["step_order"],
            service_owner=defn["service_owner"],
            kind=defn["kind"],
            description=defn["description"],
            pass_rule=defn["pass_rule"],
            source_file=defn["source_file"],
        )
