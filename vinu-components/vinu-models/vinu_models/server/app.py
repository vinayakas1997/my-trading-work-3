"""HTTP surface of the model-serving service. Liveness is `GET /models/health` (from vinu_infra.server.create_app);
the per-angle picture is `GET /models/status`."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vinu_infra.server import create_app as _create_app
from vinu_models.service import ModelError, ModelService


class AngleRequest(BaseModel):
    symbol: str
    bars: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    from_ts: int | None = None
    to_ts: int | None = None
    time_format: str | None = None


class FinbertRequest(BaseModel):
    texts: list[str]
    batch_size: int = 16


def _raise(exc: ModelError) -> None:
    raise HTTPException(status_code=exc.status, detail={"reason": exc.reason, "message": exc.message})


def build_router(service: ModelService) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    def status(deep: bool = False) -> dict[str, Any]:
        return service.status(deep=deep)

    @router.get("/angles")
    def angles() -> dict[str, Any]:
        return {"angles": sorted(service.angles())}

    @router.post("/angle/{angle}/compute")
    async def compute(angle: str, body: AngleRequest) -> dict[str, Any]:
        try:
            return await service.compute_angle(angle, body.model_dump())
        except ModelError as exc:
            _raise(exc)
            raise

    @router.post("/finbert/score")
    async def finbert(body: FinbertRequest) -> dict[str, Any]:
        try:
            return await service.score_finbert(body.texts, body.batch_size)
        except ModelError as exc:
            _raise(exc)
            raise

    return router


def create_app(service: ModelService | None = None):
    svc = service or ModelService(
        max_concurrent=int(os.getenv("VINU_MODELS_MAX_CONCURRENT", "1")),
        timeout_sec=float(os.getenv("VINU_MODELS_TIMEOUT_SEC", "600")),
        allow_proxy=os.getenv("VINU_MODELS_ALLOW_PROXY", "true").strip().lower() in ("1", "true", "yes", "on"),
    )
    return _create_app(
        service_name="vinu-models",
        version="0.1.0",
        description="Model-serving service: the model-category analysis angles and FinBERT (the only place torch is needed)",
        router=build_router(svc),
        route_prefix="models",
    )
