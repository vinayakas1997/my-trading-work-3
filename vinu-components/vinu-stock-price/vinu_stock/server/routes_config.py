"""Configuration, watchlist, and trigger routes."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from vinu_stock.server.schemas import (
    SettingsPatchRequest,
    SettingsResponse,
    TriggerResponse,
    WatchlistAddRequest,
    WatchlistResponse,
)
from vinu_stock.service import StockService

router = APIRouter(tags=["config"])

_background_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_backfill_lock = threading.Lock()
_ingest_lock = threading.Lock()
_JOBS_MAX = 50


def _cleanup_old_jobs() -> None:
    """Remove oldest entries when dict exceeds max size (caller must hold _jobs_lock)."""
    while len(_background_jobs) > _JOBS_MAX:
        oldest = next(iter(_background_jobs))
        del _background_jobs[oldest]


def _get_running_job_id(job_type: str) -> str | None:
    with _jobs_lock:
        for jid, job in _background_jobs.items():
            if job.get("type") == job_type and job.get("status") == "running":
                return jid
    return None


def get_service() -> StockService:
    raise RuntimeError("StockService dependency not configured")


@router.get("/settings", response_model=SettingsResponse)
def read_settings() -> SettingsResponse:
    view = get_service().get_settings()
    return SettingsResponse(
        poll_interval_sec=view.poll_interval_sec,
        default_provider=view.default_provider,
        data_root=view.data_root,
    )


@router.patch("/settings", response_model=SettingsResponse)
def patch_settings(body: SettingsPatchRequest) -> SettingsResponse:
    view = get_service().patch_settings(
        poll_interval_sec=body.poll_interval_sec,
        default_provider=body.default_provider,
        data_root=body.data_root,
    )
    return SettingsResponse(
        poll_interval_sec=view.poll_interval_sec,
        default_provider=view.default_provider,
        data_root=view.data_root,
    )


@router.get("/watchlist/tickers", response_model=WatchlistResponse)
def list_watchlist() -> WatchlistResponse:
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.post("/watchlist/tickers", response_model=WatchlistResponse)
def add_watchlist_tickers(body: WatchlistAddRequest) -> WatchlistResponse:
    get_service().add_watchlist_tickers(body.tickers)
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.delete("/watchlist/tickers/{symbol}", response_model=WatchlistResponse)
def remove_watchlist_ticker(symbol: str) -> WatchlistResponse:
    get_service().remove_watchlist_ticker(symbol)
    return WatchlistResponse(tickers=get_service().get_watchlist())


@router.post("/watchlist/sync")
def sync_watchlist() -> dict:
    result = get_service().sync_watchlist_from_shared()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("message")))
    return result


class BackfillRequest(BaseModel):
    symbols: list[str] | None = None
    force: bool = False


@router.post("/backfill/trigger", response_model=TriggerResponse)
def trigger_backfill(req: BackfillRequest = Body(default=None)) -> TriggerResponse:
    if not _backfill_lock.acquire(blocking=False):
        running_job_id = _get_running_job_id("backfill")
        detail = "Backfill already running"
        if running_job_id:
            detail = f"Backfill already running (job_id={running_job_id})"
        raise HTTPException(status_code=409, detail=detail)
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _background_jobs[job_id] = {"type": "backfill", "status": "running", "summary": {}}
        _cleanup_old_jobs()

    def _run() -> None:
        try:
            symbols = req.symbols if req is not None else None
            force = req.force if req is not None else False
            from_year = 2022 if force else None
            result = get_service().run_backfill(symbols=symbols, from_year=from_year)
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "backfill",
                    "status": "done",
                    "summary": {
                        "years_ok": result.summary.years_ok,
                        "years_failed": result.summary.years_failed,
                        "total_rows": result.summary.total_rows,
                        "symbols_skipped": result.summary.symbols_skipped,
                        "rows_rolled": result.summary.rows_rolled,
                    },
                }
                _cleanup_old_jobs()
        except Exception as exc:
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "backfill",
                    "status": "failed",
                    "summary": {},
                    "error": str(exc),
                }
                _cleanup_old_jobs()
        finally:
            _backfill_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})


@router.get("/backfill/status/{job_id}")
def backfill_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _background_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/ingest/trigger", response_model=TriggerResponse)
def trigger_ingest() -> TriggerResponse:
    if not _ingest_lock.acquire(blocking=False):
        running_job_id = _get_running_job_id("ingest")
        detail = "Ingest already running"
        if running_job_id:
            detail = f"Ingest already running (job_id={running_job_id})"
        raise HTTPException(status_code=409, detail=detail)
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _background_jobs[job_id] = {"type": "ingest", "status": "running", "summary": {}}
        _cleanup_old_jobs()

    def _run() -> None:
        try:
            result = get_service().run_live_cycle()
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "ingest",
                    "status": "done",
                    "summary": {
                        "bars_added": result.summary.bars_added,
                        "symbols_polled": result.summary.symbols_polled,
                        "watchlist_size": result.watchlist_size,
                    },
                }
                _cleanup_old_jobs()
        except Exception as exc:
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "ingest",
                    "status": "failed",
                    "summary": {},
                    "error": str(exc),
                }
                _cleanup_old_jobs()
        finally:
            _ingest_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})
