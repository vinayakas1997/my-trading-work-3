from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vinu_research.config import load_config

router = APIRouter()

_service = None


def set_service(svc: Any) -> None:
    global _service
    _service = svc


@router.get("/health")
async def health() -> dict[str, Any]:
    if _service is None:
        return {"status": "error", "message": "Service not initialized"}
    return _service.health()


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    config = load_config()
    return {
        "features_api_url": config.features_api_url,
        "simulator_api_url": config.simulator_api_url,
        "correlation_api_url": config.correlation_api_url,
        "max_iterations": config.max_iterations,
        "initial_capital": config.initial_capital,
        "data_root": str(config.data_root),
    }
