from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from vinu_correlation.server.schemas import DataResponse, StoryResponse

router = APIRouter()

get_service = None


@router.get("/impact/{ticker}")
def get_impact(
    ticker: str,
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> DataResponse:
    svc = get_service()
    data = svc.get_impact(ticker, from_ts=from_, to_ts=to)
    return DataResponse(count=len(data.get("events", [])), data=data)


@router.get("/events/{ticker}")
def get_events(
    ticker: str,
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> DataResponse:
    svc = get_service()
    data = svc.get_events(ticker, from_ts=from_, to_ts=to)
    return DataResponse(count=len(data), data=data)


@router.get("/correlation/{ticker}")
def get_correlation(
    ticker: str,
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> dict[str, Any]:
    svc = get_service()
    return svc.get_correlation(ticker, from_ts=from_, to_ts=to)


@router.get("/drawdown/{ticker}")
def get_drawdown(
    ticker: str,
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> dict[str, Any]:
    svc = get_service()
    return svc.get_drawdown(ticker, from_ts=from_, to_ts=to)


@router.get("/baseline/{ticker}")
def get_baseline(ticker: str) -> dict[str, Any]:
    svc = get_service()
    return svc.get_baseline(ticker)


@router.get("/story/{ticker}")
def get_story(
    ticker: str,
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> StoryResponse:
    svc = get_service()
    data = svc.get_story(ticker, from_ts=from_, to_ts=to)
    return StoryResponse(ticker=ticker, data=data)


@router.get("/correlation/batch")
def get_batch(
    symbols: str = Query(..., description="Comma-separated ticker symbols"),
    from_: int | None = Query(None, alias="from"),
    to: int | None = Query(None, alias="to"),
) -> dict[str, Any]:
    svc = get_service()
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return svc.get_batch(sym_list, from_ts=from_, to_ts=to)


@router.get("/gap/{ticker}")
def get_gap(
    ticker: str,
    date: str | None = Query(None, description="ISO date e.g. 2026-07-06"),
) -> dict[str, Any]:
    svc = get_service()
    return svc.get_gap(ticker, date=date)
