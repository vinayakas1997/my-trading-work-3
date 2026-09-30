"""Step 9's read-only HTTP surface (system-wide-audit-and-design/
00-overview.md, 02-open-questions-strategy-and-simulation.md): the first
real consumer (`get_reflection_synthesis`, vinu-agent's Planner) reads
the brain's already-durable output over HTTP instead of importing this
package back in-process, which would be a circular dependency (every
intended consumer is already a dependency *of* vinu-reflection).

Read-only by design, matching the brain's own constraint: this route
never accepts a write. The worker loop (`brain.run_synthesis()`) remains
the only writer to `reflection_synthesis_outcomes`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from vinu_infra.reflection import ReflectionStore

router = APIRouter()

_store: ReflectionStore | None = None


def set_store(store: ReflectionStore) -> None:
    global _store
    _store = store


def _require_store() -> ReflectionStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _store


@router.get("/synthesis/latest")
async def get_latest_synthesis_route() -> dict[str, Any]:
    """Most recent synthesis outcome on file, whether resolved or still
    pending -- `{"status": "none"}` when the brain has never written one
    (e.g. `brain_synthesis_enabled` is off, or no cycle has fired yet),
    never a 404 -- "no synthesis yet" is an expected, common state for a
    reader to handle, not an error."""
    store = _require_store()
    row = store.get_latest_synthesis()
    if row is None:
        return {"status": "none"}
    return {"status": "ok", "synthesis": row}


@router.get("/synthesis/pending")
async def list_pending_syntheses_route(
    as_of: float | None = Query(default=None),
) -> dict[str, Any]:
    """Synthesis outcomes past their own `resolve_by` with no resolution
    recorded yet -- honest raw rows, same posture as every other
    read-only introspection route in this codebase."""
    store = _require_store()
    rows = store.list_pending_syntheses(as_of)
    return {"syntheses": rows, "count": len(rows)}


@router.get("/beliefs/notable")
async def list_notable_beliefs_route(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """A6 fix: every belief currently notable/significant, across all
    clusters -- the same set the brain itself synthesizes from
    (`gather_synthesis_inputs`), exposed so advisory consumers (e.g.
    vinu-agent's live-decision context) can cite "Regime cluster:
    degrading" without importing this package in-process (same
    cross-process rule `get_reflection_synthesis` already follows).
    Honest raw rows, newest first by store order; `{"beliefs": [],
    "count": 0}` most cycles -- most scopes are routine, which is the
    expected outcome, not a gap. Read-only, like every route here."""
    from vinu_reflection.reflection.brain import gather_synthesis_inputs

    store = _require_store()
    rows = gather_synthesis_inputs(store)[:limit]
    return {"beliefs": rows, "count": len(rows)}
