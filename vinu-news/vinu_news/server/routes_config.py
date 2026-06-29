"""Configuration and watchlist HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vinu_news.server.schemas import (
    SettingsPatchRequest,
    SettingsResponse,
    WatchlistAddRequest,
    WatchlistResponse,
)
from vinu_news.service import NewsService

router = APIRouter(tags=["config"])


def get_service() -> NewsService:
    raise RuntimeError("NewsService dependency not configured")


@router.get("/settings", response_model=SettingsResponse)
def read_settings() -> SettingsResponse:
    service = get_service()
    view = service.get_settings()
    return SettingsResponse(mode=view.mode, poll_interval_sec=view.poll_interval_sec)


@router.patch("/settings", response_model=SettingsResponse)
def patch_settings(body: SettingsPatchRequest) -> SettingsResponse:
    service = get_service()
    try:
        view = service.patch_settings(
            mode=body.mode,
            poll_interval_sec=body.poll_interval_sec,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SettingsResponse(mode=view.mode, poll_interval_sec=view.poll_interval_sec)


@router.get("/watchlist/tickers", response_model=WatchlistResponse)
def list_watchlist() -> WatchlistResponse:
    service = get_service()
    return WatchlistResponse(tickers=service.get_watchlist())


@router.post("/watchlist/tickers", response_model=WatchlistResponse)
def add_watchlist_tickers(body: WatchlistAddRequest) -> WatchlistResponse:
    service = get_service()
    service.add_watchlist_tickers(body.tickers)
    return WatchlistResponse(tickers=service.get_watchlist())


@router.delete("/watchlist/tickers/{symbol}", response_model=WatchlistResponse)
def remove_watchlist_ticker(symbol: str) -> WatchlistResponse:
    service = get_service()
    service.remove_watchlist_ticker(symbol)
    return WatchlistResponse(tickers=service.get_watchlist())
