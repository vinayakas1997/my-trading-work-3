"""HTTP routes for feature catalog, alpha factors, and ML models."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from vinu_tools.compute.feature_catalog import format_help, get_indicator, indicator_meta_to_dict, list_indicators
from vinu_tools.server.schemas import FeatureCatalogResponse, IndicatorMetaOut
from vinu_tools.server.routes_requests import get_service

LOG = logging.getLogger(__name__)
_REATTEMPTS = 3
_BACKOFF = 1.5

router = APIRouter(tags=["catalog"])


async def _run_sync[T](fn, *args, **kwargs) -> T:
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


# ── Alpha Factor endpoints ─────────────────────────────────────


@router.get("/factors")
async def list_factors(group: str | None = None) -> dict[str, Any]:
    """List all alpha factors, optionally filtered by group."""
    svc = get_service()
    factors = await _run_sync(svc.list_factors)
    if group:
        factors = [f for f in factors if f.get("group") == group]
    return {"count": len(factors), "data": factors}


@router.get("/factors/search")
async def search_factors(q: str = Query(..., description="Search query")) -> dict[str, Any]:
    """Search alpha factors by concept."""
    svc = get_service()
    results = await _run_sync(svc.search_factors, q)
    return {"count": len(results), "data": results}


@router.get("/factors/{factor_id}")
async def get_factor(factor_id: str) -> dict[str, Any]:
    """Get full spec for a factor (description, formula, params)."""
    svc = get_service()
    spec = await _run_sync(svc.get_factor_spec, factor_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return spec


@router.post("/factors/{factor_id}/bench")
async def bench_factor(
    factor_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Bench a factor. Body must contain panel data or be empty (uses last known).
    
    For now this is a placeholder that returns metadata. Full benching
    requires market data that the HTTP layer doesn't currently serve.
    """
    svc = get_service()
    spec = await _run_sync(svc.get_factor_spec, factor_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return {
        "id": factor_id,
        "message": "Bench via CLI with actual market data: vinu-tools factors bench",
        "spec": spec,
    }


# ── ML Model endpoints ─────────────────────────────────────────


@router.get("/ml/models")
async def list_ml_models() -> dict[str, Any]:
    """List available ML models."""
    svc = get_service()
    models = await _run_sync(svc.list_ml_models)
    return {"count": len(models), "data": models}


# ── Indicator catalog + symbol snapshot (registered LAST so the
#    /{symbol_or_kind} catch-all can't shadow the specific routes above) ──


@router.get("/catalog", response_model=FeatureCatalogResponse)
def list_features() -> FeatureCatalogResponse:
    data = [IndicatorMetaOut(**indicator_meta_to_dict(m)) for m in list_indicators()]
    return FeatureCatalogResponse(count=len(data), data=data)


@router.get("/{symbol_or_kind}")
async def get_feature_or_symbol(symbol_or_kind: str, indicators: str | None = None) -> Any:
    from vinu_tools.compute.feature_catalog import list_indicators, get_indicator, format_help

    known_kinds = {m.kind.lower() for m in list_indicators()}
    is_known = False
    for k in known_kinds:
        if symbol_or_kind.lower() == k or symbol_or_kind.lower().startswith(k + "_"):
            is_known = True
            break

    if is_known:
        try:
            meta = get_indicator(symbol_or_kind)
        except ValueError as exc:
            parts = symbol_or_kind.split("_")
            if len(parts) > 1:
                prefix = parts[0]
                try:
                    meta = get_indicator(prefix)
                except ValueError:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
            else:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        out = IndicatorMetaOut(**indicator_meta_to_dict(meta))
        out.help_text = format_help(meta.kind)
        return out
    else:
        svc = get_service()
        url = f"{svc.config.stock_api_url.rstrip('/')}/stock/candles/{symbol_or_kind.upper()}"
        params = {"days": 60}
        if indicators:
            params["indicators"] = indicators
        try:
            delay = 1.0
            last_exc: Exception | None = None
            for attempt in range(_REATTEMPTS):
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(url, params=params, timeout=10.0)
                    resp.raise_for_status()
                    data = resp.json()
                    candles = data.get("data", [])
                    break
                except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                    last_exc = e
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in (429, 500, 502, 503, 504):
                        raise
                    if attempt == _REATTEMPTS - 1:
                        raise
                    LOG.warning("Transient error on GET %s (attempt %s/%s): %s",
                                url, attempt + 1, _REATTEMPTS, e)
                    await asyncio.sleep(delay)
                    delay *= _BACKOFF
                    continue
            if last_exc:
                raise last_exc
        except Exception as exc:
            LOG.error("Failed to fetch features from stock-api: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"Upstream stock-api error for {symbol_or_kind}: {exc}",
            ) from exc

        if not candles:
            return {"symbol": symbol_or_kind, "values": {}, "signal": 0.0}

        latest = candles[-1]

        ind_names = [i.strip().lower() for i in indicators.split(",")] if indicators else []
        values = {}
        for name in ind_names:
            values[name] = latest.get(name, 0.0)

        signal = latest.get("signal", 0.0)
        return {
            "symbol": symbol_or_kind,
            "values": values,
            "signal": signal
        }

