"""Read-only candle and catalog routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from vinu_stock.query.indicators import parse_indicator_names
from vinu_stock.server.schemas import CandlesBatchRequest, CandlesBatchResponse, DataResponse
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


@router.post("/candles/batch", response_model=CandlesBatchResponse)
def candles_batch(body: CandlesBatchRequest) -> CandlesBatchResponse:
    """One round-trip for many symbols' candles, instead of one call per
    symbol -- built for `vinu-screener`'s ~8000-symbol poll cycle, which
    had no bulk endpoint to call (confirmed while building its data-source
    adapter; the timeout guard + coarse filter + rate-limit floor there are
    mitigations for this gap, not a fix for it). POST, not GET, because a
    few thousand symbols in a query string doesn't fit; capped at
    `StockService.MAX_BATCH_SYMBOLS` per call so one request can't stall
    the event loop indefinitely."""
    service = get_service()
    if len(body.symbols) > service.MAX_BATCH_SYMBOLS:
        raise HTTPException(
            status_code=422,
            detail=f"at most {service.MAX_BATCH_SYMBOLS} symbols per batch call, got {len(body.symbols)}",
        )
    try:
        indicator_list = parse_indicator_names(",".join(body.indicators)) if body.indicators else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw = service.get_candles_batch(
        body.symbols,
        interval=body.interval,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        days=body.days,
        provider=body.provider,
        limit=body.limit,
        indicators=indicator_list,
        adjusted=body.adjusted,
    )
    results = {symbol: DataResponse(count=len(rows), data=rows) for symbol, rows in raw.items()}
    empty = sorted(sym for sym, rows in raw.items() if not rows)
    if empty:
        # Same "don't let an empty result silently look like success" concern
        # candles()'s X-Data-Empty header addresses -- a batch call has no
        # single header to carry that per-symbol, so it's logged instead;
        # results[symbol].count == 0 is the per-symbol signal callers read.
        LOG.warning("candles batch: %d/%d symbols empty (%s)", len(empty), len(body.symbols),
                    ", ".join(empty[:20]) + ("..." if len(empty) > 20 else ""))
    return CandlesBatchResponse(results=results)
