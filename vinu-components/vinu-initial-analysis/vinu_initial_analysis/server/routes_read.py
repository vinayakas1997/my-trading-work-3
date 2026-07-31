from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from vinu_initial_analysis.pnl_attribution_ingest import ingest_closed_positions
from vinu_initial_analysis.service import InitialAnalysisService

router = APIRouter()
get_service: Any = None


def _get_svc() -> InitialAnalysisService:
    svc = get_service() if callable(get_service) else get_service
    if svc is None:
        raise HTTPException(503, "Service not available")
    return svc


@router.get("/impact/{ticker}")
def get_impact(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_impact(ticker.upper(), from_ts, to_ts)


@router.get("/events/{ticker}")
def get_events(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_events(ticker.upper(), from_ts, to_ts)


@router.get("/correlation/batch")
def get_batch(symbols: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return svc.get_batch(sym_list, from_ts, to_ts)


@router.get("/correlation/{ticker}")
def get_correlation(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_correlation(ticker.upper(), from_ts, to_ts)


@router.get("/drawdown/{ticker}")
def get_drawdown(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_drawdown(ticker.upper(), from_ts, to_ts)


@router.get("/story/{ticker}")
def get_story(ticker: str, from_ts: int | None = Query(None), to_ts: int | None = Query(None)):
    svc = _get_svc()
    return svc.get_story(ticker.upper(), from_ts, to_ts)


# -- new initial-analysis endpoints ----------------------------------------


@router.get("/angles")
def list_angles():
    svc = _get_svc()
    return {"angles": svc.list_angles()}


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and value != value:
        return None
    return value


@router.get("/angle/{angle_name}/{ticker}")
def get_angle(angle_name: str, ticker: str):
    svc = _get_svc()
    df = svc.storage.read(ticker.upper(), angle_name)
    records = df.to_dict("records") if not df.empty else []
    records = [{k: _json_safe(v) for k, v in rec.items()} for rec in records]
    return {
        "symbol": ticker.upper(),
        "angle": angle_name,
        "row_count": len(records),
        "data": records,
    }


@router.post("/run/{ticker}")
def run_analysis(
    ticker: str,
    from_ts: int | None = Query(None),
    to_ts: int | None = Query(None),
    angle_names: str | None = Query(
        None, description="Comma-separated angle names to run; omit to run all angles",
    ),
):
    svc = _get_svc()
    names = [n.strip() for n in angle_names.split(",") if n.strip()] if angle_names else None
    return svc.run_analysis(ticker.upper(), from_ts, to_ts, angle_names=names)


class RecordPnlAttributionRequest(BaseModel):
    closed_positions: list[dict[str, Any]]


@router.post("/pnl-attribution/{ticker}/record")
def record_pnl_attribution(ticker: str, body: RecordPnlAttributionRequest) -> dict[str, Any]:
    """Phase 7's push-fed write path into the pnl_attribution angle (see
    angles/pnl_attribution/spec.yaml for why this doesn't go through /run/{ticker})."""
    svc = _get_svc()
    run_id = ingest_closed_positions(svc.storage, ticker.upper(), body.closed_positions)
    return {"symbol": ticker.upper(), "run_id": run_id, "n_recorded": len(body.closed_positions)}


@router.get("/symbols")
def list_symbols():
    svc = _get_svc()
    return {"symbols": svc.list_symbols()}
