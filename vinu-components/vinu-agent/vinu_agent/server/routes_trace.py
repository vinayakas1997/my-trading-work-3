"""Pillar 7's traceability query, made whole: given any one reference id you
already have in hand -- a Telegram session id, a vinu-research artifact id,
a team run id -- pull together everything else the system knows that's
linked to it, from one call, instead of chasing it by hand across
`trade_audit.log`, `team_runs.db`, and `strategy_store.db` separately.

Deliberately a read-only aggregator over stores that already exist (see
`broker/kill_switch.py`'s `AuditLogger.search()`, `storage/team_runs.py`'s
`list_by_artifact_id`/`list_by_session_id`, vinu-research's `strategy_store`
via `broker/research_link.py`'s in-process link) -- no new id scheme
introduced, no new store. `artifact_id` was already the best-threaded id in
the system (research run -> trade plan -> approval -> live order's
`client_order_id` -> performance tracking); this route is what was actually
missing: a single place that follows it (or a session id) end to end. Each
source is independently best-effort -- one store being briefly unavailable
must not 500 the other three sections, same fail-soft posture the rest of
this codebase applies to cross-store reads.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

router = APIRouter()

LOG = logging.getLogger(__name__)

_get_service: Any = lambda: None


def _team_run_to_dict(run: Any) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "team_name": run.team_name,
        "triggered_by_session_id": run.triggered_by_session_id,
        "status": run.status,
        "verdict": run.verdict,
        "related_artifact_id": run.related_artifact_id,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def _artifact_to_dict(artifact: Any) -> dict[str, Any]:
    status = getattr(artifact, "status", None)
    return {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "name": artifact.name,
        "status": getattr(status, "value", status),
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
        "source_run_id": artifact.source_run_id,
        "initial_sharpe": artifact.initial_sharpe,
        "deflated_sharpe": artifact.deflated_sharpe,
    }


@router.get("/trace/{ref_id}")
async def trace(ref_id: str) -> dict[str, Any]:
    svc = _get_service()

    audit_entries: list[dict[str, Any]] = []
    try:
        from ..broker.kill_switch import AuditLogger

        audit_entries = AuditLogger.search(ref_id)
    except Exception:
        LOG.exception("trace: audit log search failed for %s, continuing without it", ref_id)

    team_runs: list[dict[str, Any]] = []
    try:
        store = svc.team_run_store if svc is not None else None
        if store is not None:
            by_artifact = store.list_by_artifact_id(ref_id)
            by_session = store.list_by_session_id(ref_id)
            seen = {r.run_id for r in by_artifact}
            team_runs = [_team_run_to_dict(r) for r in by_artifact]
            team_runs += [_team_run_to_dict(r) for r in by_session if r.run_id not in seen]
    except Exception:
        LOG.exception("trace: team_run_store lookup failed for %s, continuing without it", ref_id)

    artifact: dict[str, Any] | None = None
    try:
        strategy_store = svc.strategy_store if svc is not None else None
        if strategy_store is not None:
            found = strategy_store.get_artifact(ref_id)
            if found is not None:
                artifact = _artifact_to_dict(found)
    except Exception:
        LOG.exception("trace: strategy_store lookup failed for %s, continuing without it", ref_id)

    performance: dict[str, Any] | None = None
    try:
        from ..broker.performance_store import get_store as get_performance_store

        perf_store = get_performance_store()
        meta = perf_store.get_meta(ref_id)
        returns = perf_store.get_daily_returns(ref_id)
        if meta or returns:
            performance = {"meta": meta, "daily_returns": returns}
    except Exception:
        LOG.exception("trace: performance_store lookup failed for %s, continuing without it", ref_id)

    found_anything = bool(audit_entries or team_runs or artifact or performance)
    return {
        "ref_id": ref_id,
        "found": found_anything,
        "audit_entries": audit_entries,
        "team_runs": team_runs,
        "artifact": artifact,
        "performance": performance,
    }
