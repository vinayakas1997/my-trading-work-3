from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vinu_strategy.config import load_config

router = APIRouter()


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
