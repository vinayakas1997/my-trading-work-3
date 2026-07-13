from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from vinu_strategy.config import load_config

router = APIRouter()

_service = None


def set_service(svc: Any) -> None:
    global _service
    _service = svc


@router.get("/health")
async def health() -> dict[str, Any]:
    global _service
    if _service is None:
        return {"status": "error", "message": "Service not initialized"}
    config = _service._config
    deps = {}
    for name, url in [("features", config.features_api_url), ("correlation", config.correlation_api_url)]:
        try:
            res = httpx.get(f"{url}/health", timeout=2.0)
            deps[name] = {"reachable": True, "status_code": res.status_code}
        except Exception as e:
            deps[name] = {"reachable": False, "error": str(e)}
    return {
        "status": "ok",
        "service": "vinu-strategy",
        "features_api_healthy": deps.get("features", {}).get("reachable", False),
        "correlation_api_healthy": deps.get("correlation", {}).get("reachable", False),
        "total_strategies": len(_service._registry.list_strategies()),
        "db_size_bytes": _service._meta_storage._db_path.stat().st_size if _service._meta_storage._db_path.exists() else 0,
    }


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    config = load_config()
    return {
        "host": config.host,
        "port": config.port,
        "data_root": str(config.data_root),
        "strategies_dir": str(config.strategies_dir),
        "features_api_url": config.features_api_url,
        "correlation_api_url": config.correlation_api_url,
        "max_weight": config.max_weight,
        "cash_floor": config.cash_floor,
        "rebalance_freq": config.rebalance_freq,
    }
