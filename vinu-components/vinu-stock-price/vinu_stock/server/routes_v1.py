"""The redesigned positional API — /v1/stage1/vinu-stock-price/{action}/{ticker}/{granularity}/{time-range}[/{run-id}]

Full spec: New-talk-/Final-implementation/03-actual-plan-findings/02-api-design.md

This is additive, alongside the existing /stock/* routes (routes_read.py,
routes_config.py) — those aren't removed, since health/catalog/watchlist/
settings/global-backfill are operational routes outside the per-ticker
fetch/trigger shape this file implements.

Design notes specific to this component (raw price data, Tier 1 — see
02-storage-plan.md):
  - `tier` in the response envelope is always "tier1" here. The envelope's
    tier field was designed primarily to distinguish tier2 (scheduled) vs
    tier3 (triggered) for vinu-initial-analysis's angle runs; raw price
    data doesn't have that distinction, so "tier1" (raw, append-only) is
    the natural extension of the same naming, not a new concept.
  - `trigger` always ingests at 1m from the provider and stores raw
    (per 03-storage-design.md section 3: "fetch only 1min, resample the
    rest"). {granularity} in a trigger call is validated (must be a known
    value) but doesn't change what gets fetched — resampling to coarser
    granularities happens at `fetch` time via the existing query engine.
  - `trigger`'s job tracking is an in-memory dict, matching the existing
    pattern already used by this same component's /backfill/trigger and
    /ingest/trigger routes (routes_config.py) — not the SQL-run-log
    pattern from 03-storage-design.md section 7, which is specifically
    about resolving "latest analysis run" for vinu-initial-analysis's
    angles. This is a raw ingest trigger, not an analysis run; matching
    this component's own existing convention is the more consistent
    choice than importing a pattern designed for a different problem.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from vinu_stock.service import StockService

router = APIRouter(tags=["v1-stage1"])

_GRANULARITY_MAP: dict[str, str] = {
    "1min": "1m",
    "5min": "5m",
    "15min": "15m",
    "1hr": "1h",
    "4hr": "4h",
    "1day": "1d",
}

_PAGE_SIZE = 500
_JOBS_MAX = 200


def get_service() -> StockService:
    raise RuntimeError("StockService dependency not configured")


class Envelope(BaseModel):
    run_id: str | None
    status: str
    computed_at: str | None
    tier: str
    data: Any


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _cleanup_old_jobs() -> None:
    while len(_jobs) > _JOBS_MAX:
        oldest = next(iter(_jobs))
        del _jobs[oldest]


def _parse_granularity(raw: str) -> str:
    key = raw.strip().lower()
    if key not in _GRANULARITY_MAP:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported granularity '{raw}'. Supported: {sorted(_GRANULARITY_MAP)}",
        )
    return _GRANULARITY_MAP[key]


def _parse_time_range(raw: str) -> tuple[int, int]:
    parts = raw.split("_")
    if len(parts) != 2:
        raise HTTPException(
            status_code=422,
            detail="time-range must be '{start-iso}_{end-iso}', e.g. "
            "2022-01-01T00:00:00_2026-06-30T23:59:59",
        )
    try:
        start = datetime.fromisoformat(parts[0])
        end = datetime.fromisoformat(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid time-range timestamps: {exc}") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def _fetch_page(ticker: str, interval: str, start_ts: int, end_ts: int, page: int) -> list[dict[str, Any]]:
    service = get_service()
    offset = max(0, page - 1) * _PAGE_SIZE
    rows = service.get_candles(
        ticker.upper(), interval=interval, from_ts=start_ts, to_ts=end_ts, limit=offset + _PAGE_SIZE
    )
    return rows[offset : offset + _PAGE_SIZE]


@router.get("/fetch/{ticker}/{granularity}/{time_range}", response_model=Envelope)
def fetch(
    response: Response,
    ticker: str,
    granularity: str,
    time_range: str,
    page: int = Query(default=1, ge=1),
) -> Envelope:
    interval = _parse_granularity(granularity)
    start_ts, end_ts = _parse_time_range(time_range)
    rows = _fetch_page(ticker, interval, start_ts, end_ts, page)
    if not rows:
        response.status_code = 404
        return Envelope(run_id=None, status="not_found", computed_at=None, tier="tier1", data=None)
    return Envelope(
        run_id=None,
        status="ok",
        computed_at=datetime.now(timezone.utc).isoformat(),
        tier="tier1",
        data=rows,
    )


@router.get("/fetch/{ticker}/{granularity}/{time_range}/{run_id}", response_model=Envelope)
def fetch_by_run(response: Response, ticker: str, granularity: str, time_range: str, run_id: str) -> Envelope:
    with _jobs_lock:
        job = _jobs.get(run_id)
    if job is None:
        response.status_code = 404
        return Envelope(run_id=run_id, status="not_found", computed_at=None, tier="tier1", data=None)
    if job["status"] == "running":
        response.status_code = 202
        return Envelope(run_id=run_id, status="computing", computed_at=None, tier="tier1", data=None)
    if job["status"] == "failed":
        return Envelope(
            run_id=run_id,
            status="failed",
            computed_at=job.get("computed_at"),
            tier="tier1",
            data={"error": job.get("error")},
        )
    # done -> the ingested data is now in storage under the plain fetch path.
    # page=1 explicitly: this is a direct Python call, not a FastAPI-routed
    # request, so the Query(...) sentinel default on fetch() would not be
    # resolved to an int here.
    return fetch(response, ticker, granularity, time_range, page=1)


@router.post("/trigger/{ticker}/{granularity}/{time_range}", response_model=Envelope, status_code=202)
def trigger(ticker: str, granularity: str, time_range: str) -> Envelope:
    _parse_granularity(granularity)  # validated but not used — see module docstring
    start_ts, end_ts = _parse_time_range(time_range)
    service = get_service()
    run_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[run_id] = {"status": "running", "computed_at": None}
        _cleanup_old_jobs()

    start_year = datetime.fromtimestamp(start_ts, tz=timezone.utc).year
    end_year = datetime.fromtimestamp(end_ts, tz=timezone.utc).year
    sym = ticker.upper()

    def _run() -> None:
        try:
            service.run_backfill(symbols=[sym], from_year=start_year, to_year=end_year)
            with _jobs_lock:
                _jobs[run_id] = {"status": "done", "computed_at": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            with _jobs_lock:
                _jobs[run_id] = {
                    "status": "failed",
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }

    threading.Thread(target=_run, daemon=True).start()
    return Envelope(run_id=run_id, status="computing", computed_at=None, tier="tier1", data=None)
