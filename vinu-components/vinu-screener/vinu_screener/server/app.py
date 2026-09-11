"""The last "wire it up" piece: a FastAPI app exposing `RuleStore` CRUD,
B19's dry-run, and B20's pairlist HTTP surface as one running process.

Deliberately does NOT run `Scheduler.run_forever()` inside this app's own
event loop -- the polling loop is its own process (`vinu-screener scan`,
`cli.py`), same "one process, one job" convention `vinu-portfolio`'s
`serve` / `monitor` CLI split already uses (see `drawdown_scheduler.py`).
Bundling a blocking poll loop into the API process's lifespan would either
block the event loop (sync) or need its own thread/task management this
app has no reason to own -- a separate process restarts independently,
scales independently, and can't wedge the HTTP API if the scan loop hangs.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vinu_infra.auth import VINU_API_KEY
from vinu_infra.server import create_app as _create_app

from ..audit.watch_history import WatchAuditStore
from ..features.library import FeatureLibrary
from ..rules.store import RuleStore
from ..scan.data_source import HttpStockDataSource, SymbolDataSource
from ..scan.dry_run import run_dry_run
from ..scan.monitor import ScanMonitor, ScanRule
from ..serve.pairlist_cache import PairlistCache
from ..serve.router import build_router

DEFAULT_DATA_ROOT = Path(os.environ.get("VINU_SCREENER_DATA_ROOT", str(Path.home() / ".vinu")))
DEFAULT_RULE_DB_PATH = os.environ.get("VINU_SCREENER_RULE_DB", str(DEFAULT_DATA_ROOT / "screener_rules.db"))
DEFAULT_AUDIT_DB_PATH = os.environ.get("VINU_SCREENER_AUDIT_DB", str(DEFAULT_DATA_ROOT / "screener_audit.db"))
# VINU_STOCK_API_URL is the bare cross-service URL (e.g. http://stock-api:8081
# in Docker Compose, matching every other vinu-* consumer's env-var
# convention -- see .env-example's "Cross-service API URLs" section); each
# consumer appends its own service's route prefix, same as
# vinu_research.tools.ResearchTools does for this same upstream.
DEFAULT_STOCK_API_URL = os.environ.get("VINU_STOCK_API_URL", "http://localhost:8081").rstrip("/") + "/stock"
# The pairlist route (B20) is mounted inside this same app's `router`, which
# `vinu_infra.server.create_app` wraps in `Depends(require_auth)` for the
# WHOLE app whenever VINU_API_KEY is set -- so the same `Authorization`
# header has to satisfy that outer check AND this route's own bearer check
# below. Defaulting to VINU_API_KEY itself (rather than an empty string)
# means the common case (one shared internal token, VINU_API_KEY set,
# VINU_SCREENER_PAIRLIST_TOKEN left unset) just works with one token, not
# two that would otherwise silently conflict and 401 every request. An
# operator who genuinely wants a distinct pairlist-only token still can --
# they'd need VINU_API_KEY unset (open API, pairlist-gated only) for it to
# actually take effect, since a double-gate on the same header can't pass
# two different token values.
DEFAULT_PAIRLIST_TOKEN = os.environ.get("VINU_SCREENER_PAIRLIST_TOKEN") or VINU_API_KEY
DEFAULT_PAIRLIST_TTL_SEC = float(os.environ.get("VINU_SCREENER_PAIRLIST_TTL_SEC", "60.0"))


class RuleUpsertRequest(BaseModel):
    condition: dict
    universe: list[str]
    cooldown_min: float = 0.0
    coarse_filter: dict = {}
    actions: dict = {}
    mode: str = "persistent"
    interval_sec: float = 60.0
    active: bool = True


def create_app(
    *,
    rule_store: RuleStore | None = None,
    audit_store: WatchAuditStore | None = None,
    data_source: SymbolDataSource | None = None,
):
    store = rule_store or RuleStore(DEFAULT_RULE_DB_PATH)
    audit = audit_store or WatchAuditStore(DEFAULT_AUDIT_DB_PATH)
    ds = data_source or HttpStockDataSource(httpx.Client(), base_url=DEFAULT_STOCK_API_URL)
    library = FeatureLibrary()
    owns_stores = rule_store is None and audit_store is None

    def _monitor() -> ScanMonitor:
        # One shared FeatureLibrary, fresh cache cleared each cycle by
        # run_cycle() itself (B4's own cache-scoping rule) -- reused across
        # requests here is just avoiding a pointless object churn.
        return ScanMonitor(ds, library=library)

    router = APIRouter()

    @router.get("/screener/rules")
    def list_rules() -> dict:
        return {"rules": [s.to_dict() for s in store.all()]}

    @router.get("/screener/rules/{rule_id}")
    def get_rule(rule_id: str) -> dict:
        stored = store.get(rule_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="rule not found")
        return stored.to_dict()

    @router.put("/screener/rules/{rule_id}")
    def upsert_rule(rule_id: str, body: RuleUpsertRequest) -> dict:
        try:
            rule = ScanRule.from_dict({
                "rule_id": rule_id,
                "condition": body.condition,
                "universe": body.universe,
                "cooldown_min": body.cooldown_min,
                "coarse_filter": body.coarse_filter,
                "actions": body.actions,
                "mode": body.mode,
            })
        except Exception as exc:  # noqa: BLE001 -- a malformed rule body is a 422, not a 500
            raise HTTPException(status_code=422, detail=str(exc)) from None
        stored = store.upsert_rule(rule, interval_sec=body.interval_sec, active=body.active)
        return stored.to_dict()

    @router.delete("/screener/rules/{rule_id}")
    def delete_rule(rule_id: str) -> dict:
        return {"status": "ok", "deleted": store.delete(rule_id)}

    @router.post("/screener/rules/{rule_id}/enable")
    def enable_rule(rule_id: str) -> dict:
        if store.get(rule_id) is None:
            raise HTTPException(status_code=404, detail="rule not found")
        store.set_active(rule_id, True)
        return {"status": "ok", "rule_id": rule_id, "active": True}

    @router.post("/screener/rules/{rule_id}/disable")
    def disable_rule(rule_id: str) -> dict:
        if store.get(rule_id) is None:
            raise HTTPException(status_code=404, detail="rule not found")
        store.set_active(rule_id, False)
        return {"status": "ok", "rule_id": rule_id, "active": False}

    @router.post("/screener/rules/{rule_id}/dry-run")
    def dry_run_rule(rule_id: str) -> dict:
        """B19: validate a rule against current data before it runs
        unattended, with the same triggered/not_triggered/evaluation_error/
        degraded/skipped counts DSA's own dry-run UX reports. Never touches
        the rule's live cooldown state (`run_dry_run`'s own guarantee)."""
        stored = store.get(rule_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="rule not found")
        report = run_dry_run(_monitor(), stored.rule)
        return {
            "rule_id": rule_id,
            "counts": report.counts,
            "triggered": report.triggered,
            "not_triggered": report.not_triggered,
            "evaluation_error": report.evaluation_error,
            "degraded": report.degraded,
            "skipped": report.skipped,
        }

    @router.get("/screener/rules/{rule_id}/history")
    def fired_history(rule_id: str, limit: int = 100) -> dict:
        from dataclasses import asdict

        return {"rule_id": rule_id, "history": [asdict(h) for h in audit.history(rule_id=rule_id, limit=limit)]}

    def _refresh_pairlist(rule_id: str) -> list[str]:
        stored = store.get(rule_id)
        if stored is None:
            raise KeyError(f"no such rule: {rule_id}")
        return _monitor().run_cycle(stored.rule).fired

    pairlist_cache = PairlistCache(refresh_fn=_refresh_pairlist, ttl_sec=DEFAULT_PAIRLIST_TTL_SEC)
    router.include_router(build_router(pairlist_cache, bearer_token=DEFAULT_PAIRLIST_TOKEN))

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owns_stores:
            store.close()
            audit.close()

    app = _create_app(
        service_name="vinu-screener",
        version="0.1.0",
        description="Rule-based full-market scanner — condition schema, scan loop, filter/score/risk-overlay pipeline",
        router=router,
        lifespan=lifespan,
    )
    return app
