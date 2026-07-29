from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from vinu_lib.server import create_app as _create_app
from vinu_simulator.service import SimulatorService


def create_app(service: SimulatorService | None = None):
    app_service = service or SimulatorService()

    import vinu_simulator.server.routes_read as rr
    rr._get_service = lambda: app_service

    import vinu_simulator.server.routes_config as rc

    def _settings():
        from vinu_simulator.config import load_config
        cfg = load_config()
        return {
            "initial_capital": cfg.initial_capital,
            "transaction_cost_pct": cfg.transaction_cost_pct,
            "slippage_pct": cfg.slippage_pct,
            "benchmark_tickers": list(cfg.benchmark_tickers),
            "allow_short": cfg.allow_short,
            "strategy_api_url": cfg.strategy_api_url,
            "stock_api_url": cfg.stock_api_url,
            "features_api_url": cfg.features_api_url,
            "deviation_threshold": cfg.deviation_threshold,
        }

    rc._get_settings = _settings

    merged = APIRouter()
    merged.include_router(rr.router, tags=["read"])
    merged.include_router(rc.router, tags=["config"])

    return _create_app(
        service_name="vinu-simulator",
        version="0.1.0",
        description="Backtesting engine — realistic simulation with slippage, commission, position accounting",
        router=merged,
        static_dir=Path(__file__).resolve().parent / "static",
        expose_health_on_root=True,
        route_prefix="simulator",
    )
