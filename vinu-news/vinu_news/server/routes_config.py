"""Configuration and watchlist HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vinu_news.server.schemas import (
    SettingsPatchRequest,
    SettingsResponse,
    ToggleEnabledRequest,
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
    return SettingsResponse(
        mode=view.mode,
        poll_interval_sec=view.poll_interval_sec,
        llm_analysis_mode=view.llm_analysis_mode,
        llm_analysis_concurrency=view.llm_analysis_concurrency,
    )


@router.patch("/settings", response_model=SettingsResponse)
def patch_settings(body: SettingsPatchRequest) -> SettingsResponse:
    service = get_service()
    try:
        view = service.patch_settings(
            mode=body.mode,
            poll_interval_sec=body.poll_interval_sec,
            llm_analysis_mode=body.llm_analysis_mode,
            llm_analysis_concurrency=body.llm_analysis_concurrency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SettingsResponse(
        mode=view.mode,
        poll_interval_sec=view.poll_interval_sec,
        llm_analysis_mode=view.llm_analysis_mode,
        llm_analysis_concurrency=view.llm_analysis_concurrency,
    )


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


@router.post("/watchlist/sync")
def sync_watchlist() -> dict:
    service = get_service()
    result = service.sync_watchlist_from_shared()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("message")))
    return result


@router.post("/ingest/ticker-news")
def ingest_ticker_news(days: int = 7) -> dict:
    service = get_service()
    result = service.run_ticker_news_ingest(days=days)
    return {
        "ok": True,
        "raw_count": result.raw_count,
        "inserted": result.inserted,
        "watchlist_size": result.watchlist_size,
    }


@router.get("/feeds")
def list_feeds(all: bool = False) -> dict:
    from vinu_news.rss.config.feed_loader import load_feeds
    try:
        feeds = load_feeds(only_enabled=not all)
        return {
            "feeds": [
                {
                    "id": f.id,
                    "url": f.url,
                    "source": f.source,
                    "region": f.region,
                    "tier": f.tier,
                    "category": f.category,
                    "enabled": f.enabled,
                }
                for f in feeds
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/feeds/{feed_id}")
def toggle_feed(feed_id: str, body: ToggleEnabledRequest) -> dict:
    from vinu_news.rss.config.feed_loader import set_feed_enabled
    try:
        feed = set_feed_enabled(feed_id, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": feed.id,
        "url": feed.url,
        "source": feed.source,
        "region": feed.region,
        "tier": feed.tier,
        "category": feed.category,
        "enabled": feed.enabled,
    }


@router.get("/providers")
def list_providers() -> dict:
    from vinu_news.providers.config.loader import load_ticker_news_providers
    configs = load_ticker_news_providers()
    return {
        "providers": [{"id": c.id, "enabled": c.enabled, "priority": c.priority} for c in configs]
    }


@router.patch("/providers/{provider_id}")
def toggle_provider(provider_id: str, body: ToggleEnabledRequest) -> dict:
    from vinu_news.providers.config.loader import set_provider_enabled
    try:
        provider = set_provider_enabled(provider_id, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": provider.id, "enabled": provider.enabled, "priority": provider.priority}
