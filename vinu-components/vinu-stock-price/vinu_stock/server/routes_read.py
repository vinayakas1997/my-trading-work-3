"""Read-only candle and catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vinu_stock.query.indicators import parse_indicator_names
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
    indicators: str | None = Query(default=None, description="Comma-separated indicator names"),
    adjusted: bool = Query(default=False),
) -> DataResponse:
    service = get_service()
    try:
        indicator_list = parse_indicator_names(indicators)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = service.get_candles(
        symbol,
        interval=interval,
        from_ts=from_ts,
        to_ts=to_ts,
        days=days,
        provider=provider,
        limit=limit,
        indicators=indicator_list or None,
        adjusted=adjusted,
    )
    return DataResponse(count=len(rows), data=rows)
