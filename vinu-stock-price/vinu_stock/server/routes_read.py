"""Read-only candle and catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vinu_stock.server.schemas import DataResponse
from vinu_stock.service import StockService

router = APIRouter(tags=["prices"])


def get_service() -> StockService:
    raise RuntimeError("StockService dependency not configured")


@router.get("/health")
def health() -> dict:
    return get_service().health()


@router.get("/catalog", response_model=DataResponse)
def list_catalog() -> DataResponse:
    rows = get_service().get_catalog()
    return DataResponse(count=len(rows), data=rows)


@router.get("/catalog/{symbol}", response_model=DataResponse)
def symbol_catalog(symbol: str) -> DataResponse:
    rows = get_service().get_catalog(symbol)
    if not rows:
        raise HTTPException(status_code=404, detail="Symbol not in catalog")
    return DataResponse(count=len(rows), data=rows)


@router.get("/candles/{symbol}", response_model=DataResponse)
def candles(
    symbol: str,
    interval: str = Query(default="1m"),
    from_ts: int | None = Query(default=None, alias="from"),
    to_ts: int | None = Query(default=None, alias="to"),
    days: int | None = Query(default=None, ge=1, le=3650),
    provider: str | None = None,
    limit: int = Query(default=5000, ge=1, le=50000),
) -> DataResponse:
    service = get_service()
    rows = service.get_candles(
        symbol,
        interval=interval,
        from_ts=from_ts,
        to_ts=to_ts,
        days=days,
        provider=provider,
        limit=limit,
    )
    return DataResponse(count=len(rows), data=rows)
