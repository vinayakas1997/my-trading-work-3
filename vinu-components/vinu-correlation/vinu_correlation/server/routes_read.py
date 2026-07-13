from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from vinu_correlation.server.schemas import DataResponse

router = APIRouter()

get_service = None


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


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
