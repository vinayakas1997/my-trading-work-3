"""Read-only news consumption HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vinu_news.server.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DataResponse,
    ThreadDetailResponse,
)
from vinu_news.service import NewsService

router = APIRouter(tags=["news"])


def get_service() -> NewsService:
    raise RuntimeError("NewsService dependency not configured")


@router.get("/health")
def health() -> dict:
    service = get_service()
    return service.health()


@router.get("/latest", response_model=DataResponse)
def latest(limit: int = Query(default=20, ge=1, le=500)) -> DataResponse:
    service = get_service()
    rows = service.get_latest(limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/ticker/{symbol}", response_model=DataResponse)
def ticker_news(
    symbol: str,
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.get_ticker_news(symbol, days=days, limit=limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/watchlist/news", response_model=DataResponse)
def watchlist_news(
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.get_watchlist_news(days=days, limit=limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/search", response_model=DataResponse)
def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.search(q, limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/high-impact", response_model=DataResponse)
def high_impact(
    hours: int = Query(default=24, ge=1, le=720),
    sentiment: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.get_high_impact(hours=hours, sentiment=sentiment, limit=limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/threads/active", response_model=DataResponse)
def active_threads(
    hours: int = Query(default=48, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.get_active_threads(hours=hours, limit=limit)
    return DataResponse(count=len(rows), data=rows)


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
def thread_detail(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> ThreadDetailResponse:
    service = get_service()
    detail = service.get_thread_detail(thread_id, limit=limit)
    if not detail:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadDetailResponse(**detail)


@router.get("/threads/{thread_id}/timeline", response_model=DataResponse)
def thread_timeline(thread_id: str) -> DataResponse:
    service = get_service()
    rows = service.get_thread_timeline(thread_id)
    return DataResponse(count=len(rows), data=rows)


@router.get("/stats/ticker/{symbol}", response_model=DataResponse)
def ticker_stats(
    symbol: str,
    days: int = Query(default=7, ge=1, le=365),
) -> DataResponse:
    service = get_service()
    rows = service.get_ticker_stats(symbol, days=days)
    return DataResponse(count=len(rows), data=rows)


@router.get("/articles/since", response_model=DataResponse)
def articles_since(
    ts: int = Query(description="Unix timestamp (seconds)"),
    limit: int = Query(default=100, ge=1, le=500),
) -> DataResponse:
    service = get_service()
    rows = service.get_articles_since(ts, limit)
    return DataResponse(count=len(rows), data=rows)


@router.post("/news/analyze", response_model=AnalyzeResponse)
def analyze_news(body: AnalyzeRequest) -> AnalyzeResponse:
    service = get_service()
    try:
        result = service.analyze_article(body.url_or_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AnalyzeResponse(**result)
