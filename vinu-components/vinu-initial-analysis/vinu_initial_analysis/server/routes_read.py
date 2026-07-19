from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from vinu_initial_analysis.service import InitialAnalysisService

router = APIRouter()
get_service: Any = None


def _get_svc() -> InitialAnalysisService:
    svc = get_service() if callable(get_service) else get_service
    if svc is None:
        raise HTTPException(503, "Service not available")
    return svc


@router.get("/impact/{ticker}")
async def get_impact(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_impact(ticker.upper(), from_ts, to_ts)


@router.get("/events/{ticker}")
async def get_events(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_events(ticker.upper(), from_ts, to_ts)


@router.get("/correlation/{ticker}")
async def get_correlation(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_correlation(ticker.upper(), from_ts, to_ts)


@router.get("/drawdown/{ticker}")
async def get_drawdown(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_drawdown(ticker.upper(), from_ts, to_ts)


@router.get("/story/{ticker}")
async def get_story(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_story(ticker.upper(), from_ts, to_ts)


@router.get("/correlation/batch")
async def get_batch(symbols: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return svc.get_batch(sym_list, from_ts, to_ts)


# -- new initial-analysis endpoints ----------------------------------------


@router.get("/angles")
async def list_angles():
    svc = _get_svc()
    return {"angles": svc.list_angles()}


@router.get("/angle/{angle_name}/{ticker}")
async def get_angle(angle_name: str, ticker: str):
    svc = _get_svc()
    df = svc.storage.read(ticker.upper(), angle_name)
    return {
        "symbol": ticker.upper(),
        "angle": angle_name,
        "row_count": len(df),
        "data": df.to_dict("records") if not df.empty else [],
    }


@router.post("/run/{ticker}")
async def run_analysis(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.run_analysis(ticker.upper(), from_ts, to_ts)


@router.get("/symbols")
async def list_symbols():
    svc = _get_svc()
    return {"symbols": svc.list_symbols()}
