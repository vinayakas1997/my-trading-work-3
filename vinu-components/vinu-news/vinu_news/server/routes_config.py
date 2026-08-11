"""Configuration and watchlist HTTP routes."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from vinu_news.server.schemas import (
    SettingsPatchRequest,
    SettingsResponse,
    ToggleEnabledRequest,
    WatchlistAddRequest,
    WatchlistResponse,
)
from vinu_news.server.schemas import BackfillToggleRequest, IngestTriggerResponse
from vinu_news.service import NewsService

router = APIRouter(tags=["config"])

_background_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_backfill_lock = threading.Lock()
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


def get_service() -> NewsService:
    raise RuntimeError("NewsService dependency not configured")


@router.get("/settings", response_model=SettingsResponse)
def read_settings() -> SettingsResponse:
    service = get_service()
    view = service.get_settings()
    return SettingsResponse(
        mode=view.mode,
        poll_interval_sec=view.poll_interval_sec,
        active_tiers=view.active_tiers,
        backfill_start_date=view.backfill_start_date,
        backfill_pause_on_error=view.backfill_pause_on_error,
    )


@router.patch("/settings", response_model=SettingsResponse)
def patch_settings(body: SettingsPatchRequest) -> SettingsResponse:
    service = get_service()
    try:
        view = service.patch_settings(
            mode=body.mode,
            poll_interval_sec=body.poll_interval_sec,
            active_tiers=body.active_tiers,
            backfill_start_date=body.backfill_start_date,
            backfill_pause_on_error=body.backfill_pause_on_error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SettingsResponse(
        mode=view.mode,
        poll_interval_sec=view.poll_interval_sec,
        active_tiers=view.active_tiers,
        backfill_start_date=view.backfill_start_date,
        backfill_pause_on_error=view.backfill_pause_on_error,
    )


@router.get("/watchlist/tickers", response_model=WatchlistResponse)
def list_watchlist() -> WatchlistResponse:
    service = get_service()
    return WatchlistResponse(tickers=service.get_watchlist())


@router.post("/watchlist/tickers", response_model=WatchlistResponse)
def add_watchlist_tickers(body: WatchlistAddRequest) -> WatchlistResponse:
    service = get_service()
    service.add_watchlist_tickers(body.tickers)
    return WatchlistResponse(tickers=service.get_watchlist())


@router.delete("/watchlist/tickers/{symbol}", response_model=WatchlistResponse)
def remove_watchlist_ticker(symbol: str) -> WatchlistResponse:
    service = get_service()
    service.remove_watchlist_ticker(symbol)
    return WatchlistResponse(tickers=service.get_watchlist())


@router.post("/watchlist/sync")
def sync_watchlist() -> dict:
    service = get_service()
    result = service.sync_watchlist_from_shared()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("message")))
    return result


@router.post("/ingest/ticker-news")
def ingest_ticker_news(days: int = 7) -> dict:
    service = get_service()
    result = service.run_ticker_news_ingest(days=days)
    return {
        "ok": True,
        "raw_count": result.raw_count,
        "inserted": result.inserted,
        "watchlist_size": result.watchlist_size,
    }


@router.get("/feeds")
def list_feeds(all: bool = False) -> dict:
    from vinu_news.rss.config.feed_loader import load_feeds
    try:
        feeds = load_feeds(only_enabled=not all)
        return {
            "feeds": [
                {
                    "id": f.id,
                    "url": f.url,
                    "source": f.source,
                    "region": f.region,
                    "tier": f.tier,
                    "category": f.category,
                    "enabled": f.enabled,
                }
                for f in feeds
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/feeds/{feed_id}")
def toggle_feed(feed_id: str, body: ToggleEnabledRequest) -> dict:
    from vinu_news.rss.config.feed_loader import set_feed_enabled
    try:
        feed = set_feed_enabled(feed_id, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": feed.id,
        "url": feed.url,
        "source": feed.source,
        "region": feed.region,
        "tier": feed.tier,
        "category": feed.category,
        "enabled": feed.enabled,
    }


@router.get("/providers")
def list_providers() -> dict:
    from vinu_news.providers.config.loader import load_ticker_news_providers
    configs = load_ticker_news_providers()
    return {
        "providers": [{"id": c.id, "enabled": c.enabled, "priority": c.priority} for c in configs]
    }


@router.patch("/providers/{provider_id}")
def toggle_provider(provider_id: str, body: ToggleEnabledRequest) -> dict:
    from vinu_news.providers.config.loader import set_provider_enabled
    try:
        provider = set_provider_enabled(provider_id, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": provider.id, "enabled": provider.enabled, "priority": provider.priority}


@router.get("/backfill/status")
def backfill_status() -> dict:
    service = get_service()
    return {"backfill_status": service.get_backfill_status()}


@router.post("/backfill/{ticker}/toggle")
def toggle_backfill(ticker: str, body: BackfillToggleRequest) -> dict:
    service = get_service()
    service.toggle_backfill(ticker, body.enabled)
    return {"ticker": ticker.upper(), "enabled": body.enabled}


@router.post("/ingest/trigger", response_model=IngestTriggerResponse, tags=["ingest"])
def trigger_ingest():
    import time
    service = get_service()
    service.set_poll_status(last_poll_started_at=int(time.time()))
    result = service.run_ingestion_cycle()
    service.set_poll_status(
        last_poll_finished_at=int(time.time()),
        last_raw_count=result.raw_count,
        last_leads_before_filter=result.leads_before_filter,
        last_leads_after_filter=result.leads_after_filter,
        last_inserted=result.inserted,
    )
    return IngestTriggerResponse(
        ok=True,
        summary={
            "inserted": result.inserted,
            "mode": result.mode,
            "leads_after_filter": result.leads_after_filter,
            "raw_count": result.raw_count,
        },
    )


@router.post("/backfill/trigger", response_model=IngestTriggerResponse)
def trigger_backfill(ticker: str | None = None) -> IngestTriggerResponse:
    if not _backfill_lock.acquire(blocking=False):
        running_job_id = _get_running_job_id("backfill")
        detail = "Backfill already running"
        if running_job_id:
            detail = f"Backfill already running (job_id={running_job_id})"
        raise HTTPException(status_code=409, detail=detail)
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _background_jobs[job_id] = {"type": "backfill", "status": "running", "results": []}
        _cleanup_old_jobs()

    def _run() -> None:
        try:
            service = get_service()
            if ticker:
                result = service.run_backfill_single(ticker)
            else:
                result = service.run_backfill_all()
            results = result if isinstance(result, list) else [result]
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "backfill",
                    "status": "done",
                    "results": results,
                }
                _cleanup_old_jobs()
        except Exception as exc:
            with _jobs_lock:
                _background_jobs[job_id] = {
                    "type": "backfill",
                    "status": "failed",
                    "results": [],
                    "error": str(exc),
                }
                _cleanup_old_jobs()
        finally:
            _backfill_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return IngestTriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})


@router.get("/backfill/job/{job_id}")
def backfill_job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _background_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


_finbert_lock = threading.Lock()


@router.post("/finbert/backfill", response_model=IngestTriggerResponse)
def trigger_finbert_backfill(batch_size: int = 500) -> IngestTriggerResponse:
    """Score all articles missing finbert_score, in batches, until none remain."""
    if not _finbert_lock.acquire(blocking=False):
        running_job_id = _get_running_job_id("finbert")
        detail = "FinBERT backfill already running"
        if running_job_id:
            detail = f"FinBERT backfill already running (job_id={running_job_id})"
        raise HTTPException(status_code=409, detail=detail)
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _background_jobs[job_id] = {"type": "finbert", "status": "running", "scored_total": 0}
        _cleanup_old_jobs()

    def _run() -> None:
        try:
            service = get_service()
            total = 0
            while True:
                result = service.backfill_finbert_sentiment(limit=batch_size)
                total += result["scored"]
                with _jobs_lock:
                    _background_jobs[job_id] = {
                        "type": "finbert", "status": "running", "scored_total": total,
                        "remaining": result["remaining"],
                    }
                if result["scored"] == 0 or result["remaining"] == 0:
                    break
            with _jobs_lock:
                _background_jobs[job_id] = {"type": "finbert", "status": "done", "scored_total": total}
                _cleanup_old_jobs()
        except Exception as exc:
            with _jobs_lock:
                _background_jobs[job_id] = {"type": "finbert", "status": "failed", "error": str(exc)}
                _cleanup_old_jobs()
        finally:
            _finbert_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return IngestTriggerResponse(ok=True, summary={"job_id": job_id, "status": "running"})


@router.get("/finbert/job/{job_id}")
def finbert_job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _background_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
