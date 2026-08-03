"""Feature request HTTP routes."""

from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query

from vinu_tools.server.schemas import (
    FeatureRequestIn,
    FeatureRequestListResponse,
    FeatureRequestOut,
    FeatureSpecIn,
    HealthResponse,
    PresetListResponse,
    PresetOut,
)
from vinu_tools.service import FeatureService

router = APIRouter(tags=["features"])

_service: FeatureService | None = None


def get_service() -> FeatureService:
    if _service is None:
        raise RuntimeError("FeatureService dependency not configured")
    return _service


def set_service(svc: FeatureService) -> None:
    global _service
    _service = svc


async def _run_sync[T](fn, *args, **kwargs) -> T:
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    info = await _run_sync(get_service().health_info)
    return HealthResponse(info=info)


@router.get("/presets", response_model=PresetListResponse)
async def presets() -> PresetListResponse:
    rows = await _run_sync(get_service().list_presets)
    data = [PresetOut(**row) for row in rows]
    return PresetListResponse(count=len(data), data=data)


@router.post("/requests", response_model=FeatureRequestOut)
async def create_request(body: FeatureRequestIn) -> FeatureRequestOut:
    features_payload: list[str | dict] = []
    for item in body.features:
        if isinstance(item, FeatureSpecIn):
            features_payload.append(item.model_dump())
        else:
            features_payload.append(item)
    try:
        req = await _run_sync(
            get_service().submit,
            title=body.title,
            symbols=body.symbols,
            from_ts=body.from_ts,
            to_ts=body.to_ts,
            days=body.days,
            interval=body.interval,
            preset=body.preset,
            features=features_payload,
            conditions=body.conditions,
            ml_model=body.ml_model,
            ml_label=body.ml_label,
            run_immediately=body.run_immediately,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeatureRequestOut.from_model(req)


@router.get("/requests", response_model=FeatureRequestListResponse)
async def list_requests(
    status: str | None = None,
    title: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> FeatureRequestListResponse:
    rows = await _run_sync(get_service().list_requests, status=status, title=title, limit=limit)
    data = [FeatureRequestOut.from_model(r) for r in rows]
    return FeatureRequestListResponse(count=len(data), data=data)


@router.get("/requests/{request_id}", response_model=FeatureRequestOut)
async def get_request(request_id: int) -> FeatureRequestOut:
    req = await _run_sync(get_service().get_request, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.get("/requests/by-title/{title}", response_model=FeatureRequestOut)
async def get_by_title(title: str) -> FeatureRequestOut:
    req = await _run_sync(get_service().get_by_title, title)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.get("/requests/{request_id}/data")
async def get_request_data(request_id: int) -> dict:
    try:
        return await _run_sync(get_service().get_request_data, request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/requests/{request_id}/run", response_model=FeatureRequestOut)
async def run_request(request_id: int) -> FeatureRequestOut:
    req = await _run_sync(get_service().run_request, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.delete("/requests/{request_id}", response_model=FeatureRequestOut)
async def delete_request(request_id: int) -> FeatureRequestOut:
    req = await _run_sync(get_service().delete_request, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)
