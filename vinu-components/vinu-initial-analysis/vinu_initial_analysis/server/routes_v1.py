"""The redesigned positional API — /v1/stage1/vinu-initial-analysis/{action}/{ticker}/{granularity}/{time-range}/{method}[/{run-id}]

Full spec: New-talk-/Final-implementation/03-actual-plan-findings/02-api-design.md

This is additive, alongside the existing /analysis/* routes
(routes_read.py, routes_config.py) — those aren't removed.

Design notes specific to this component:
  - `{method}` is required (this is the one component the original API
    design always intended it for — see 02-api-design.md's table).
  - `tier` in the response envelope reflects the actual storage tier the
    result came from (`tier2`/`tier3`), read straight off the RunLog row
    that `AngleStorage._resolve_latest_path()` resolved — this is the
    real thing 02-api-design.md's envelope was designed around.
  - **Fixed (was a known limitation)**: `trigger` now threads the parsed
    `{granularity}` through as `AngleRunner.run(..., time_format=...)`,
    which restricts that run to computing just the one requested
    time_format and writes/records it under that exact `granularity` —
    not the storage default of `"1D"` regardless of what was actually
    computed. `fetch`/`fetch_by_run` already read by the requested
    granularity correctly; this closes the other half (the write side
    silently ignoring it). Every other, unrestricted call site of
    `AngleRunner.run()` (e.g. the tier2 scheduler, which wants every
    declared time_format combined into one write) is unchanged — `time_format`
    is opt-in, `None` preserves the prior default behavior exactly.
    `AngleRunner._run_angle` also now rejects (`ValueError`) a requested
    time_format the angle doesn't actually declare, rather than silently
    computing something it wasn't asked to support.
  - `trigger` pre-assigns `run_id` and threads it through
    `AngleRunner.run(..., run_id=...)` so the ID returned immediately at
    trigger-time is the exact same one that ends up in `RunLog`/storage —
    not a separately-generated one reconciled after the fact. See
    `runner.py`'s `run()` docstring for why this only works for a
    single-angle call (which `trigger/.../{method}` always is).
  - Job status tracking for `trigger` uses the same in-memory dict
    pattern as vinu-stock-price/vinu-news's v1 routes (not the SQL
    RunLog) for the "is this specific trigger call still running"
    question — once it's done, `fetch`/`fetch_by_run` both resolve the
    actual result through RunLog/AngleStorage as normal, which *is* the
    SQL-based path 03-storage-design.md calls for. The in-memory dict
    only ever answers "still running vs. finished", never "what is the
    current data" — that distinction is what keeps this consistent with
    the storage design rather than working around it.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Response

from vinu_initial_analysis.server.routes_read import _json_safe
from vinu_initial_analysis.service import InitialAnalysisService

router = APIRouter(tags=["v1-stage1"])

_GRANULARITY_MAP: dict[str, str] = {
    "1min": "1min", "5min": "5min", "15min": "15min", "1hr": "1H", "4hr": "4H", "1day": "1D",
}

_JOBS_MAX = 200


def get_service() -> InitialAnalysisService:
    raise RuntimeError("InitialAnalysisService dependency not configured")


class Envelope(dict):
    """Plain dict, not a pydantic model — angle output shapes vary too much
    per method (see each 01-present-considerations/*.md's Output format
    section) for one fixed `data` schema; the 5 envelope fields are what's
    actually fixed, `data`'s inner shape is intentionally open."""


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _cleanup_old_jobs() -> None:
    while len(_jobs) > _JOBS_MAX:
        oldest = next(iter(_jobs))
        del _jobs[oldest]


def _parse_granularity(raw: str) -> str:
    key = raw.strip().lower()
    if key not in _GRANULARITY_MAP:
        raise HTTPException(status_code=422, detail=f"Unsupported granularity '{raw}'. Supported: {sorted(_GRANULARITY_MAP)}")
    return _GRANULARITY_MAP[key]


def _parse_time_range(raw: str) -> tuple[int, int]:
    parts = raw.split("_")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="time-range must be '{start-iso}_{end-iso}'")
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


def _known_methods(svc: InitialAnalysisService) -> set[str]:
    return {a["name"] for a in svc.list_angles()}


def _records_for(svc: InitialAnalysisService, ticker: str, method: str, granularity: str, tier: str) -> list[dict[str, Any]]:
    df: pd.DataFrame = svc.storage.read(ticker, method, granularity=granularity, tier=tier)
    if df.empty:
        return []
    records = df.to_dict("records")
    return [{k: _json_safe(v) for k, v in rec.items()} for rec in records]


@router.get("/fetch/{ticker}/{granularity}/{time_range}/{method}", response_model=None)
def fetch(response: Response, ticker: str, granularity: str, time_range: str, method: str) -> Envelope:
    """Plain fetch (no run-id) always resolves the tier2 (scheduled,
    official) result — matching the API design's `fetch` semantics
    everywhere else. To see a specific triggered (tier3) run's result,
    poll it via its run_id (`fetch_by_run` below), which knows to look in
    tier3 because that's the only tier `trigger` ever writes."""
    svc = get_service()
    if method not in _known_methods(svc):
        raise HTTPException(status_code=422, detail=f"Unknown method '{method}'")
    internal_granularity = _parse_granularity(granularity)
    _parse_time_range(time_range)  # validated for shape; angle storage isn't windowed by exact ts today

    ticker = ticker.upper()
    records = _records_for(svc, ticker, method, internal_granularity, tier="tier2")
    if not records:
        response.status_code = 404
        return Envelope(run_id=None, status="not_found", computed_at=None, tier="tier2", data=None)

    return Envelope(
        run_id=None,
        status="ok",
        computed_at=datetime.now(timezone.utc).isoformat(),
        tier="tier2",
        data=records,
    )


@router.get("/fetch/{ticker}/{granularity}/{time_range}/{method}/{run_id}", response_model=None)
def fetch_by_run(response: Response, ticker: str, granularity: str, time_range: str, method: str, run_id: str) -> Envelope:
    with _jobs_lock:
        job = _jobs.get(run_id)
    if job is None:
        response.status_code = 404
        return Envelope(run_id=run_id, status="not_found", computed_at=None, tier="tier3", data=None)
    if job["status"] == "running":
        response.status_code = 202
        return Envelope(run_id=run_id, status="computing", computed_at=None, tier="tier3", data=None)
    if job["status"] == "failed":
        return Envelope(run_id=run_id, status="failed", computed_at=job.get("computed_at"), tier="tier3", data={"error": job.get("error")})

    # done (or skipped because an existing run already covered this window)
    # -> resolve the actual current result through AngleStorage/RunLog,
    # scoped to tier3 specifically: `trigger` always writes tier3 (see
    # trigger()'s call to run_analysis(..., tier="tier3")), so that's
    # where a completed triggered run's data actually lives — unlike the
    # plain fetch() route above, which is deliberately tier2-only.
    svc = get_service()
    internal_granularity = _parse_granularity(granularity)
    ticker = ticker.upper()
    records = _records_for(svc, ticker, method, internal_granularity, tier="tier3")
    if not records:
        response.status_code = 404
        return Envelope(run_id=run_id, status="not_found", computed_at=job.get("computed_at"), tier="tier3", data=None)
    return Envelope(
        run_id=run_id,
        status="ok",
        computed_at=job.get("computed_at"),
        tier="tier3",
        data=records,
    )


@router.post("/trigger/{ticker}/{granularity}/{time_range}/{method}", status_code=202, response_model=None)
def trigger(ticker: str, granularity: str, time_range: str, method: str) -> Envelope:
    svc = get_service()
    if method not in _known_methods(svc):
        raise HTTPException(status_code=422, detail=f"Unknown method '{method}'")
    internal_granularity = _parse_granularity(granularity)
    start_ts, end_ts = _parse_time_range(time_range)

    ticker = ticker.upper()
    run_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[run_id] = {"status": "running", "computed_at": None}
        _cleanup_old_jobs()

    def _run() -> None:
        try:
            svc.run_analysis(
                ticker,
                from_ts=start_ts,
                to_ts=end_ts,
                angle_names=[method],
                run_id=run_id,
                tier="tier3",
                time_format=internal_granularity,
            )
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
    return Envelope(run_id=run_id, status="computing", computed_at=None, tier="tier3", data=None)
