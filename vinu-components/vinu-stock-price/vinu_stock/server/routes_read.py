"""Read-only candle and catalog routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from vinu_stock.query.indicators import parse_indicator_names
from vinu_stock.server.schemas import DataResponse
from vinu_stock.service import StockService

router = APIRouter(tags=["prices"])

LOG = logging.getLogger(__name__)


def get_service() -> StockService:
    raise RuntimeError("StockService dependency not configured")


@router.get("/health")
def health() -> dict:
    return get_service().health()


@router.get("/quote/{symbol}")
def quote(symbol: str) -> dict:
    """Latest NBBO bid/ask/mid/spread_bps for `symbol`. Consumed by vinu-live's
    liquidity gate (how-to-make-it-live.md #13) only at order time. Always 200:
    on any upstream problem the body carries `ok: false` + `error` and the
    caller fails open. 5s TTL-cached in StockService."""
    return get_service().get_quote(symbol)


@router.get("/events/{symbol}")
def events(
    symbol: str,
    within_hours: float = Query(default=48.0, ge=1.0, le=720.0),
) -> dict:
    """Upcoming earnings / macro events for `symbol` in the next `within_hours`,
    from the locally-cached calendar (how-to-make-it-live.md #2). `blackout` is
    True iff any are found. Consumed by vinu-live's entry guard; always 200,
    caller fails open on an empty / unreachable calendar."""
    return get_service().get_events(symbol, within_hours=within_hours)


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
    response: Response,
    interval: str = Query(default="1m"),
    from_ts: int | None = Query(default=None, alias="from"),
    to_ts: int | None = Query(default=None, alias="to"),
    days: int | None = Query(default=None, ge=1, le=3650),
    provider: str | None = None,
    limit: int = Query(default=5000, ge=1, le=50000),
    indicators: str | None = Query(default=None, description="Comma-separated indicator names"),
    adjusted: bool = Query(default=True),
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
    if not rows:
        # A 200 with an empty body is indistinguishable from success --
        # callers (and operators) mistook it for "working" with zero data.
        # Keep the 200 shape, but flag it explicitly in a header + log.
        response.headers["X-Data-Empty"] = "true"
        LOG.warning(
            "candles %s %s empty (from=%s to=%s days=%s) — watchlist/backfill gap, not success",
            symbol.upper(), interval, from_ts, to_ts, days,
        )
    return DataResponse(count=len(rows), data=rows)
