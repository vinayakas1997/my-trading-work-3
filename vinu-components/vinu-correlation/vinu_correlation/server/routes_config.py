from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vinu_correlation.server.schemas import SettingsResponse

router = APIRouter()

get_service = None


@router.get("/health")
async def health() -> dict[str, Any]:
    return await get_service().health()


@router.get("/settings")
def get_settings() -> SettingsResponse:
    svc = get_service()
    cfg = svc.config
    return SettingsResponse(
        data_root=str(cfg.data_root),
        news_api_url=cfg.news_api_url,
        stock_api_url=cfg.stock_api_url,
        port=cfg.port,
        impact_high_threshold=cfg.impact_high_threshold,
        impact_medium_threshold=cfg.impact_medium_threshold,
        drawdown_min_pct=cfg.drawdown_min_pct,
        drawdown_lookback_hours=cfg.drawdown_lookback_hours,
        baseline_window_days=cfg.baseline_window_days,
        market_hours_only=cfg.market_hours_only,
        session_break_on_close=cfg.session_break_on_close,
        cache_ttl_sec=cfg.cache_ttl_sec,
        compute_poll_interval_sec=cfg.compute_poll_interval_sec,
        compact_threshold=cfg.compact_threshold,
    )
