"""Configuration, watchlist, and trigger routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vinu_stock.server.schemas import (
    SettingsPatchRequest,
    SettingsResponse,
    TriggerResponse,
    WatchlistAddRequest,
    WatchlistResponse,
)
from vinu_stock.service import StockService

router = APIRouter(tags=["config"])


def get_service() -> StockService:
    raise RuntimeError("StockService dependency not configured")


@router.get("/settings", response_model=SettingsResponse)
def read_settings() -> SettingsResponse:
    view = get_service().get_settings()
    return SettingsResponse(
        poll_interval_sec=view.poll_interval_sec,
        default_provider=view.default_provider,
        data_root=view.data_root,
    )


@router.patch("/settings", response_model=SettingsResponse)
def patch_settings(body: SettingsPatchRequest) -> SettingsResponse:
    view = get_service().patch_settings(
        poll_interval_sec=body.poll_interval_sec,
        default_provider=body.default_provider,
        data_root=body.data_root,
    )
    return SettingsResponse(
        poll_interval_sec=view.poll_interval_sec,
        default_provider=view.default_provider,
        data_root=view.data_root,
    )


@router.get("/watchlist/tickers", response_model=WatchlistResponse)
def list_watchlist() -> WatchlistResponse:
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.post("/watchlist/tickers", response_model=WatchlistResponse)
def add_watchlist_tickers(body: WatchlistAddRequest) -> WatchlistResponse:
    get_service().add_watchlist_tickers(body.tickers)
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.delete("/watchlist/tickers/{symbol}", response_model=WatchlistResponse)
def remove_watchlist_ticker(symbol: str) -> WatchlistResponse:
    get_service().remove_watchlist_ticker(symbol)
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.post("/backfill/trigger", response_model=TriggerResponse)
def trigger_backfill() -> TriggerResponse:
    result = get_service().run_backfill()
    return TriggerResponse(
        ok=True,
        summary={
            "years_ok": result.summary.years_ok,
            "years_failed": result.summary.years_failed,
            "total_rows": result.summary.total_rows,
        },
    )


@router.post("/ingest/trigger", response_model=TriggerResponse)
def trigger_ingest() -> TriggerResponse:
    result = get_service().run_live_cycle()
    return TriggerResponse(
        ok=True,
        summary={
            "bars_added": result.summary.bars_added,
            "symbols_polled": result.summary.symbols_polled,
            "watchlist_size": result.watchlist_size,
        },
    )
