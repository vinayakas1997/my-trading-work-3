"""Configuration, watchlist, and trigger routes."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

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
_backfill_lock = threading.Lock()
_ingest_lock = threading.Lock()


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


@router.post("/backfill/trigger", response_model=TriggerResponse)
def trigger_backfill() -> TriggerResponse:
    if not _backfill_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Backfill already running")
    job_id = uuid.uuid4().hex[:12]
    _background_jobs[job_id] = {"type": "backfill", "status": "running", "summary": {}}

    def _run() -> None:
        try:
            result = get_service().run_backfill()
            _background_jobs[job_id] = {
                "type": "backfill",
                "status": "done",
                "summary": {
                    "years_ok": result.summary.years_ok,
                    "years_failed": result.summary.years_failed,
                    "total_rows": result.summary.total_rows,
                },
            }
        except Exception as exc:
            _background_jobs[job_id] = {
                "type": "backfill",
                "status": "failed",
                "summary": {},
                "error": str(exc),
            }
        finally:
            _backfill_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})


@router.get("/backfill/status/{job_id}")
def backfill_status(job_id: str) -> dict:
    job = _background_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/ingest/trigger", response_model=TriggerResponse)
def trigger_ingest() -> TriggerResponse:
    if not _ingest_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Ingest already running")
    job_id = uuid.uuid4().hex[:12]
    _background_jobs[job_id] = {"type": "ingest", "status": "running", "summary": {}}

    def _run() -> None:
        try:
            result = get_service().run_live_cycle()
            _background_jobs[job_id] = {
                "type": "ingest",
                "status": "done",
                "summary": {
                    "bars_added": result.summary.bars_added,
                    "symbols_polled": result.summary.symbols_polled,
                    "watchlist_size": result.watchlist_size,
                },
            }
        except Exception as exc:
            _background_jobs[job_id] = {
                "type": "ingest",
                "status": "failed",
                "summary": {},
                "error": str(exc),
            }
        finally:
            _ingest_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})
