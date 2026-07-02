"""Feature request HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vinu_features.server.schemas import (
    FeatureRequestIn,
    FeatureRequestListResponse,
    FeatureRequestOut,
    FeatureSpecIn,
    HealthResponse,
    PresetListResponse,
    PresetOut,
)
from vinu_features.service import FeatureService

router = APIRouter(tags=["features"])


def get_service() -> FeatureService:
    raise RuntimeError("FeatureService dependency not configured")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(info=get_service().health_info())


@router.get("/presets", response_model=PresetListResponse)
def presets() -> PresetListResponse:
    rows = get_service().list_presets()
    data = [PresetOut(**row) for row in rows]
    return PresetListResponse(count=len(data), data=data)


@router.post("/requests", response_model=FeatureRequestOut)
def create_request(body: FeatureRequestIn) -> FeatureRequestOut:
    features_payload: list[str | dict] = []
    for item in body.features:
        if isinstance(item, FeatureSpecIn):
            features_payload.append(item.model_dump())
        else:
            features_payload.append(item)
    try:
        req = get_service().submit(
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
def list_requests(
    status: str | None = None,
    title: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> FeatureRequestListResponse:
    rows = get_service().list_requests(status=status, title=title, limit=limit)
    data = [FeatureRequestOut.from_model(r) for r in rows]
    return FeatureRequestListResponse(count=len(data), data=data)


@router.get("/requests/{request_id}", response_model=FeatureRequestOut)
def get_request(request_id: int) -> FeatureRequestOut:
    req = get_service().get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.get("/requests/by-title/{title}", response_model=FeatureRequestOut)
def get_by_title(title: str) -> FeatureRequestOut:
    req = get_service().get_by_title(title)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.post("/requests/{request_id}/run", response_model=FeatureRequestOut)
def run_request(request_id: int) -> FeatureRequestOut:
    req = get_service().run_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)


@router.delete("/requests/{request_id}", response_model=FeatureRequestOut)
def delete_request(request_id: int) -> FeatureRequestOut:
    req = get_service().delete_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return FeatureRequestOut.from_model(req)
