"""Stage B (B20): the FastAPI wiring around `PairlistCache` -- a bearer-
gated, TTL-cached, fail-open `GET` endpoint exposing one rule's current
ranked symbol list. Kept as a small standalone `APIRouter` (not a full app)
so whatever process ends up hosting `vinu-screener`'s HTTP surface mounts
it, same convention `vinu-agent`'s `routes_broker.py`/`routes_notify.py`
routers use.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from .pairlist_cache import PairlistCache, check_bearer_token


def build_router(cache: PairlistCache, *, bearer_token: str) -> APIRouter:
    router = APIRouter()

    @router.get("/screener/pairlist/{rule_id}")
    def get_pairlist(rule_id: str, authorization: str | None = Header(default=None)) -> dict:
        if not check_bearer_token(authorization, bearer_token):
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")
        try:
            entry = cache.get(rule_id)
        except Exception as exc:  # noqa: BLE001 -- no cache and refresh failed: nothing safe to serve
            raise HTTPException(status_code=503, detail=f"pairlist unavailable: {exc}") from None
        return {
            "rule_id": rule_id,
            "symbols": entry.symbols,
            "generated_at": entry.generated_at,
            "stale": entry.stale,
        }

    return router
