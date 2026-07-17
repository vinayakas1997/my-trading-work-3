from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vinu_initial_analysis.service import InitialAnalysisService

router = APIRouter()
get_service: Any = None


def _get_svc() -> InitialAnalysisService:
    svc = get_service() if callable(get_service) else get_service
    if svc is None:
        from fastapi import HTTPException
        raise HTTPException(503, "Service not available")
    return svc


@router.get("/health")
async def health():
    svc = _get_svc()
    return await svc.health()


@router.get("/settings")
async def settings():
    svc = _get_svc()
    cfg = svc.config
    return {
        "data_root": str(cfg.data_root),
        "news_api_url": cfg.news_api_url,
        "stock_api_url": cfg.stock_api_url,
        "host": cfg.host,
        "port": cfg.port,
        "cache_maxsize": cfg.cache_maxsize,
        "cache_ttl_sec": cfg.cache_ttl_sec,
        "compute_poll_interval_sec": cfg.compute_poll_interval_sec,
    }
